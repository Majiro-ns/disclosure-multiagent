"""ステップ実行モード エンドポイント（cmd_360k_a2d）。

パイプラインの各ステージ（M1→M2→M3→M4→M5）を1段階ずつ実行し、
中間出力をUIで確認してから次に進む「ステップ実行モード」のAPIを提供する。

エンドポイント:
  POST /api/step/start                     - ステップ実行開始（M1を即実行）
  POST /api/step/{task_id}/next            - 次の未実行ステージを1つ実行
  GET  /api/step/{task_id}/output/{stage}  - 特定ステージの出力を詳細に返す
  POST /api/step/{task_id}/run-all         - 残りのステージを全て実行（途中からautoモード相当）

後方互換:
  既存の /api/analyze/upload（autoモード）は一切変更しない。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import verify_api_key
from api.models.schemas import (
    PipelineStatus,
    StepNextResponse,
    StepOutputResponse,
    StepStartRequest,
    StepStartResponse,
)
from api.services.pipeline import (
    STAGE_SEQUENCE,
    create_task_step,
    get_task,
    run_step_async,
)

router = APIRouter(prefix="/api/step", tags=["step"])


@router.post("/start", response_model=StepStartResponse)
async def step_start(
    request: StepStartRequest,
    _auth: None = Depends(verify_api_key),
) -> StepStartResponse:
    """ステップ実行モードを開始し、M1（PDF解析）を即時実行する。

    M1が完了したらtask_idとM1出力サマリを返す。
    後続ステージは POST /api/step/{task_id}/next で1つずつ進める。
    """
    task_id = create_task_step(
        pdf_path=request.pdf_path,
        company_name=request.company_name,
        fiscal_year=request.fiscal_year,
        fiscal_month_end=request.fiscal_month_end,
        level=request.level,
        use_mock=request.use_mock,
        doc_type=request.doc_type,
        use_debug=request.use_debug,
    )

    try:
        m1_output = await run_step_async(task_id, "m1")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"M1実行エラー: {e}")

    task = get_task(task_id)
    next_stage = task.next_stage if task else "m2"

    return StepStartResponse(
        task_id=task_id,
        status="step_paused",
        next_stage=next_stage,
        m1_output=m1_output,
    )


@router.post("/{task_id}/next", response_model=StepNextResponse)
async def step_next(
    task_id: str,
    _auth: None = Depends(verify_api_key),
) -> StepNextResponse:
    """次の未実行ステージを1つ実行する。

    Returns:
        StepNextResponse:
          status="done"     - 当該ステージ完了、まだ次のステージがある
          status="all_done" - 全ステージ（M5まで）が完了した
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"タスク {task_id} が存在しません")
    if task.execution_mode != "step":
        raise HTTPException(status_code=422, detail="このタスクはステップ実行モードではありません")
    if task.next_stage == "done":
        raise HTTPException(status_code=422, detail="全ステージ完了済みです。新しいタスクを開始してください")

    stage = task.next_stage

    try:
        output = await run_step_async(task_id, stage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{stage.upper()} 実行エラー: {e}")

    task = get_task(task_id)
    all_done = task.next_stage == "done"

    return StepNextResponse(
        task_id=task_id,
        step=stage,
        status="all_done" if all_done else "done",
        next_stage=None if all_done else task.next_stage,
        output=output,
    )


@router.get("/{task_id}/output/{stage}", response_model=StepOutputResponse)
async def get_step_output(
    task_id: str,
    stage: str,
    _auth: None = Depends(verify_api_key),
) -> StepOutputResponse:
    """特定ステージの出力を詳細に返す。

    M1: セクション一覧 + 各テキスト抜粋（先頭200文字）
    M2: 適用法令一覧 + WARNING
    M3: ギャップ一覧（gap_id, section, change_type, has_gap, description）
    M4: 提案一覧（gap_id, 松竹梅のテキスト抜粋）
    M5: レポート全文
    """
    if stage not in STAGE_SEQUENCE:
        raise HTTPException(
            status_code=422,
            detail=f"不明なステージ: {stage}。有効値: {STAGE_SEQUENCE}",
        )

    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"タスク {task_id} が存在しません")
    if stage not in task.step_outputs:
        raise HTTPException(
            status_code=404,
            detail=f"ステージ {stage} はまだ実行されていません",
        )

    return StepOutputResponse(
        task_id=task_id,
        stage=stage,
        output=task.step_outputs[stage],
    )


@router.post("/{task_id}/run-all", response_model=PipelineStatus)
async def step_run_all(
    task_id: str,
    _auth: None = Depends(verify_api_key),
) -> PipelineStatus:
    """残りの全ステージを一気に実行する。

    ステップ実行の途中から「もう全部やれ」用。
    完了後にPipelineStatusを返す（task.status == "done" かつ task.result に最終出力）。
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"タスク {task_id} が存在しません")
    if task.execution_mode != "step":
        raise HTTPException(status_code=422, detail="このタスクはステップ実行モードではありません")
    if task.next_stage == "done":
        raise HTTPException(status_code=422, detail="全ステージ完了済みです。新しいタスクを開始してください")

    # 残りステージを順次実行
    start_idx = STAGE_SEQUENCE.index(task.next_stage)
    remaining = STAGE_SEQUENCE[start_idx:]

    try:
        for stage in remaining:
            # 各ステージ実行前に next_stage が更新されているか確認（安全弁）
            current_task = get_task(task_id)
            if current_task is None or current_task.next_stage == "done":
                break
            await run_step_async(task_id, stage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"実行エラー: {e}")

    return get_task(task_id)
