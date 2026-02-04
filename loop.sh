#!/bin/bash
# Ralph Loop: Autonomous development with self-improving specs
# Usage: ./loop.sh [plan|build] [max_iterations] [review_frequency]
#
# Modes:
#   plan  - Gap analysis, update implementation plan (default: 1 iteration)
#   build - Implement tasks with spec review after each iteration
#
# The build loop:
#   1. Implements one task
#   2. Reviews the log for discoveries
#   3. Updates specs if inconsistencies found
#   4. Repeats until all tasks complete

set -e

MODE=${1:-build}
REVIEW_EVERY=${3:-1}  # Review specs every N iterations (default: every iteration)

if [ "$MODE" = "plan" ]; then
    MAX_ITERATIONS=${2:-1}
    PROMPT_FILE="PROMPT_plan.md"
else
    MAX_ITERATIONS=${2:-100}
    PROMPT_FILE="PROMPT_build.md"
fi

CLAUDE_CMD="${CLAUDE_CMD:-claude}"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: $PROMPT_FILE not found"
    exit 1
fi

echo "========================================"
echo "  Ralph Loop - Une Femme Supply Chain"
echo "========================================"
echo "Mode: $MODE"
echo "Max iterations: $MAX_ITERATIONS"
echo "Spec review: every $REVIEW_EVERY iteration(s)"
echo "========================================"
echo ""

mkdir -p logs

run_claude() {
    local prompt_file=$1
    local log_file=$2

    if command -v unbuffer &> /dev/null; then
        unbuffer "$CLAUDE_CMD" -p "$(cat "$prompt_file")" \
            --allowedTools "Read,Write,Glob,Grep,Bash,Edit" \
            2>&1 | tee "$log_file"
    elif command -v stdbuf &> /dev/null; then
        stdbuf -oL "$CLAUDE_CMD" -p "$(cat "$prompt_file")" \
            --allowedTools "Read,Write,Glob,Grep,Bash,Edit" \
            2>&1 | tee "$log_file"
    else
        "$CLAUDE_CMD" -p "$(cat "$prompt_file")" \
            --allowedTools "Read,Write,Glob,Grep,Bash,Edit" \
            2>&1 | tee "$log_file"
    fi
    return ${PIPESTATUS[0]}
}

for ((i=1; i<=MAX_ITERATIONS; i++)); do
    echo ""
    echo "========================================"
    echo "  Iteration $i of $MAX_ITERATIONS ($MODE mode)"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    echo ""

    # === BUILD/PLAN PHASE ===
    BUILD_LOG="logs/loop_${MODE}_$(date '+%Y%m%d_%H%M%S')_iter${i}.log"

    run_claude "$PROMPT_FILE" "$BUILD_LOG"
    BUILD_EXIT=${PIPESTATUS[0]}

    echo ""
    echo "Build log: $BUILD_LOG"

    if [ $BUILD_EXIT -ne 0 ]; then
        echo "Claude exited with code $BUILD_EXIT, stopping loop"
        break
    fi

    # === SPEC REVIEW PHASE (build mode only) ===
    if [ "$MODE" = "build" ] && [ $((i % REVIEW_EVERY)) -eq 0 ]; then
        echo ""
        echo "----------------------------------------"
        echo "  Spec Review (iteration $i)"
        echo "----------------------------------------"

        REVIEW_LOG="logs/loop_review_$(date '+%Y%m%d_%H%M%S')_iter${i}.log"

        # Create inline review prompt that references the just-completed build log
        REVIEW_PROMPT=$(cat <<'REVIEW_EOF'
# Quick Spec Review

Review the most recent build log for spec issues and update specs if needed.

## Instructions

1. Read the most recent log file in `logs/` (the one just created)
2. Look for:
   - "Issues encountered"
   - "inconsistency"
   - "doesn't match"
   - "actually" (often indicates discovered vs expected)
   - "missing"
   - Specific values that differ from specs

3. For each finding:
   - If P0/P1 (blocking or incorrect): Update the spec file immediately
   - If P2/P3 (minor): Note in IMPLEMENTATION_PLAN.md Discoveries section

4. When updating specs:
   - Fix the specific incorrect value/statement
   - Add a revision note at the bottom:
     ```
     ## Revision History
     - [date]: [what changed] - discovered during Task X.Y
     ```

5. Output a brief summary:
   - Findings count
   - Specs updated (if any)
   - Continue building? (yes/no)

Be quick - this is a checkpoint, not a deep review.
REVIEW_EOF
)

        echo "$REVIEW_PROMPT" | "$CLAUDE_CMD" -p "$(cat -)" \
            --allowedTools "Read,Write,Glob,Grep,Bash,Edit" \
            2>&1 | tee "$REVIEW_LOG"

        echo ""
        echo "Review log: $REVIEW_LOG"
    fi

    # === CHECK COMPLETION ===
    if [ "$MODE" = "build" ]; then
        if [ -f "IMPLEMENTATION_PLAN.md" ]; then
            INCOMPLETE=$(grep -c "^\- \[ \]" IMPLEMENTATION_PLAN.md 2>/dev/null || echo "0")
            COMPLETED=$(grep -c "^\- \[x\]" IMPLEMENTATION_PLAN.md 2>/dev/null || echo "0")

            echo ""
            echo "Progress: $COMPLETED completed, $INCOMPLETE remaining"

            if [ "$INCOMPLETE" -eq 0 ]; then
                echo ""
                echo "========================================"
                echo "  All tasks complete!"
                echo "========================================"
                break
            fi
        fi
    fi

    # Push changes if git repo
    if [ -d ".git" ]; then
        git push origin HEAD 2>/dev/null || true
    fi

    echo ""
    echo "--- Iteration $i complete ---"

    sleep 2
done

echo ""
echo "========================================"
echo "  Ralph Loop Finished"
echo "========================================"
echo "Total iterations: $i"
echo "Mode: $MODE"

if [ -f "IMPLEMENTATION_PLAN.md" ]; then
    echo ""
    echo "Final status:"
    COMPLETED=$(grep -c "^\- \[x\]" IMPLEMENTATION_PLAN.md 2>/dev/null || echo "0")
    INCOMPLETE=$(grep -c "^\- \[ \]" IMPLEMENTATION_PLAN.md 2>/dev/null || echo "0")
    echo "  Completed: $COMPLETED"
    echo "  Remaining: $INCOMPLETE"
fi

# Show spec changes
if [ -d ".git" ]; then
    SPEC_CHANGES=$(git diff --name-only specs/ 2>/dev/null | wc -l | tr -d ' ')
    if [ "$SPEC_CHANGES" -gt 0 ]; then
        echo ""
        echo "Specs modified during this run:"
        git diff --name-only specs/ 2>/dev/null
    fi
fi
