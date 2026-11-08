#!/bin/bash
set -euo pipefail

# ============================================================================
# ZeroRepo Main Pipeline Runner (fixed-args version)
# Edit the variables below to match your setup.
# ============================================================================

# ---------- User-editable settings ----------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RTL_SPEC_INPUT=""
RTL_STOP_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan|--generate)
            if [[ -n "${RTL_STOP_FLAG}" ]]; then
                echo "Use only one of --plan or --generate." >&2
                exit 2
            fi
            RTL_STOP_FLAG="$1"
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
        *)
            if [[ -n "${RTL_SPEC_INPUT}" ]]; then
                echo "Only one RTL spec file, directory or project name is allowed." >&2
                exit 2
            fi
            RTL_SPEC_INPUT="$1"
            ;;
    esac
    shift
done

# RTL Mode: 设置为 true 来从 rtl_dataset 读取 spec
RTL_MODE=true
RTL_PROJECT=""  # 指定项目名称，留空则处理所有项目；命令行第一个参数优先，可传项目名或 .md 路径
RTL_PIPELINE_MODE="${RTL_PIPELINE_MODE:-planner}" # planner | legacy

# SWE Mode (传统模式)
GENERATING_PROJECT="../eat_snake"

# Azure AD authentication (for Azure OpenAI token-based auth)
export AZURE_TENANT_ID="${AZURE_TENANT_ID:-72f988bf-86f1-41af-91ab-2d7cd011db47}"
export AZURE_TOKEN_SCOPE="${AZURE_TOKEN_SCOPE:-api://feb7b661-cac7-44a8-8dc1-163b63c23df2/.default}"

CONFIG="${PROJECT_ROOT}/configs/zerorepo_config.yaml"

# 根据模式设置路径
if [[ "${RTL_MODE}" == "true" ]]; then
    RTL_DATASET="${PROJECT_ROOT}/rtl_dataset"
    RTL_OUTPUT="${PROJECT_ROOT}/rtl_outputs"

    if [[ -z "${RTL_SPEC_INPUT}" && -n "${RTL_PROJECT}" ]]; then
        RTL_SPEC_INPUT="${RTL_PROJECT}"
    fi

    if [[ "${RTL_SPEC_INPUT}" == *.md || "${RTL_SPEC_INPUT}" == */* ]]; then
        if [[ ! -f "${RTL_SPEC_INPUT}" && ! -d "${RTL_SPEC_INPUT}" ]]; then
            echo "RTL spec file or directory not found: ${RTL_SPEC_INPUT}" >&2
            exit 1
        fi
    fi

    # 确定具体项目
    if [[ -n "${RTL_SPEC_INPUT}" ]]; then
        if [[ -d "${RTL_SPEC_INPUT}" ]]; then
            PROJECT_STEM="$(basename "${RTL_SPEC_INPUT}")"
            GENERATING_PROJECT="${RTL_OUTPUT}/${PROJECT_STEM}"
        elif [[ "${RTL_SPEC_INPUT}" == *.md || "${RTL_SPEC_INPUT}" == */* ]]; then
            SPEC_BASENAME="$(basename "${RTL_SPEC_INPUT}")"
            PROJECT_STEM="${SPEC_BASENAME%.md}"
            GENERATING_PROJECT="${RTL_OUTPUT}/${PROJECT_STEM}"
        else
            GENERATING_PROJECT="${RTL_OUTPUT}/${RTL_SPEC_INPUT}"
        fi
    else
        # 处理所有项目时使用临时目录
        GENERATING_PROJECT="${RTL_OUTPUT}/_temp"
    fi

    if [[ "${RTL_PIPELINE_MODE}" == "planner" ]]; then
        if [[ -z "${RTL_SPEC_INPUT}" ]]; then
            GENERATING_PROJECT="${RTL_OUTPUT}"
        fi
        CHECKPOINT_DIR="${GENERATING_PROJECT}/plan/state/kg"
        PHASE="rtl_planner"
    else
        CHECKPOINT_DIR="${GENERATING_PROJECT}/.zerorepo"
        PHASE="rtl"
    fi
    REPO_DIR="${GENERATING_PROJECT}"
else
    CHECKPOINT_DIR="${GENERATING_PROJECT}/checkpoints"
    REPO_DIR="${GENERATING_PROJECT}/workspace"
    PHASE="all"          # all | design | implementation
fi

LOG_LEVEL="INFO"     # DEBUG | INFO | WARNING | ERROR
if [[ -n "${RTL_STOP_FLAG}" && "${PHASE}" != "rtl_planner" ]]; then
    echo "${RTL_STOP_FLAG} requires RTL_PIPELINE_MODE=planner." >&2
    exit 2
fi
LOG_FILE="${CHECKPOINT_DIR}/zerorepo.log"
if [[ "${PHASE}" == "rtl_planner" ]]; then
    LOG_FILE=""  # main.py creates <case>/run.log after resolving each spec.
fi

LLM_CONFIG=""        # e.g., "${PROJECT_ROOT}/configs/llm.yaml" (leave empty to disable)
FORCE_REBUILD=false  # true | false
RESUME=true         # true | false
DRY_RUN=false        # true | false

# ---------- Build command ----------
CMD=(
  python "${PROJECT_ROOT}/main.py"
  --config "${CONFIG}"
  --checkpoint "${CHECKPOINT_DIR}"
  --repo "${REPO_DIR}"
  --phase "${PHASE}"
  --log-level "${LOG_LEVEL}"
)

if [[ -n "${LOG_FILE}" ]]; then
  CMD+=(--log-file "${LOG_FILE}")
fi
if [[ -n "${LLM_CONFIG}" ]]; then
  CMD+=(--llm-config "${LLM_CONFIG}")
fi
if [[ "${FORCE_REBUILD}" == "true" ]]; then
  CMD+=(--force-rebuild)
fi
if [[ "${RESUME}" == "true" ]]; then
  CMD+=(--resume)
fi
if [[ "${DRY_RUN}" == "true" ]]; then
  CMD+=(--dry-run)
fi
if [[ -n "${RTL_SPEC_INPUT}" ]]; then
  CMD+=(--rtl-spec "${RTL_SPEC_INPUT}")
fi
if [[ -n "${RTL_STOP_FLAG}" ]]; then
  CMD+=("${RTL_STOP_FLAG}")
fi

# ---------- Run ----------
echo "=========================================="
echo " ZeroRepo Pipeline"
echo "=========================================="
echo " Config:     ${CONFIG}"
echo " Checkpoint: ${CHECKPOINT_DIR}"
echo " Repo:       ${REPO_DIR}"
echo " Phase:      ${PHASE}"
echo " Log Level:  ${LOG_LEVEL}"
echo " Log File:   ${LOG_FILE:-<case>/run.log}"
echo " LLM Config: ${LLM_CONFIG:-<none>}"
echo " RTL Spec:   ${RTL_SPEC_INPUT:-<all .md files in rtl_dataset, sorted>}"
echo " RTL Mode:   ${RTL_PIPELINE_MODE:-planner}"
echo " Stop After: ${RTL_STOP_FLAG:-full pipeline}"
echo " Rebuild:    ${FORCE_REBUILD}"
echo " Resume:     ${RESUME}"
echo " Dry Run:    ${DRY_RUN}"
echo "=========================================="

if [[ "${PHASE}" != "rtl_planner" ]]; then
  mkdir -p "${CHECKPOINT_DIR}"
fi
exec "${CMD[@]}"
