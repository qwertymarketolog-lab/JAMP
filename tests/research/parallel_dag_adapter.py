import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class CausalEvent:
    event_id: str
    parent_event_ids: Tuple[str, ...]
    causal_type: str  # "FORK", "WORKER_COMPLETION", "JOIN"
    worker_id: str
    logical_clock: int  # Causal Lamport Clock (P=1, WA=2, WB=2, M=3)
    payload: str


@dataclass(frozen=True)
class ExecutionSpan:
    worker_id: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class ParallelDAGState:
    stage: str = "INIT"  # "INIT", "DONE"
    delay_a: float = 0.05
    delay_b: float = 0.05
    events: Tuple[CausalEvent, ...] = ()  # Physical arrival-order log
    spans: Tuple[ExecutionSpan, ...] = ()
    merged_result: str = ""


class ParallelDAGAdapter:
    budget = 1

    def __init__(self, initial_state: ParallelDAGState):
        self._initial_state = initial_state

    def initial(self) -> ParallelDAGState:
        return self._initial_state

    def candidates(self, state: ParallelDAGState) -> List[str]:
        if state.stage == "INIT":
            return ["SPAWN_AND_JOIN"]
        return []

    def admissible(self, state: ParallelDAGState, action: str) -> bool:
        return action == "SPAWN_AND_JOIN" and state.stage == "INIT"

    def strategy(self, state: ParallelDAGState, candidates: List[str]) -> str:
        return candidates[0]

    def _worker_task(
        self, worker_id: str, delay: float, payload_val: int
    ) -> Tuple[str, float, float, int]:
        start = time.perf_counter()
        time.sleep(delay)
        end = time.perf_counter()
        return worker_id, start, end, payload_val * 2

    def apply(
        self, state: ParallelDAGState, action: str
    ) -> ParallelDAGState:
        if action != "SPAWN_AND_JOIN":
            raise ValueError(f"Unknown action: {action}")

        # 1. Parent Fork Event (P): logical clock = 1
        p_event = CausalEvent(
            event_id="evt_P",
            parent_event_ids=(),
            causal_type="FORK",
            worker_id="coordinator",
            logical_clock=1,
            payload="Parent root initialized",
        )

        physical_events_list: List[CausalEvent] = [p_event]
        spans_list: List[ExecutionSpan] = []
        worker_results: Dict[str, int] = {}

        # 2. Real OS Thread Concurrency (WA & WB)
        # Concurrent siblings WA and WB share the SAME causal logical clock = 2
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(self._worker_task, "worker_a", state.delay_a, 10)
            future_b = executor.submit(self._worker_task, "worker_b", state.delay_b, 20)

            # Record events in physical arrival order as tasks complete
            for future in as_completed([future_a, future_b]):
                w_id, start_t, end_t, res = future.result()
                spans_list.append(ExecutionSpan(worker_id=w_id, start_time=start_t, end_time=end_t))
                worker_results[w_id] = res

                # Logical clock is 2 for both sibling completion events regardless of physical arrival
                w_event = CausalEvent(
                    event_id=f"evt_{w_id.upper()}",
                    parent_event_ids=("evt_P",),
                    causal_type="WORKER_COMPLETION",
                    worker_id=w_id,
                    logical_clock=2,
                    payload=f"Result={res}",
                )
                physical_events_list.append(w_event)

        # 3. Join Event (M): logical clock = 3 (max(parent_clocks) + 1)
        join_event = CausalEvent(
            event_id="evt_M",
            parent_event_ids=("evt_WORKER_A", "evt_WORKER_B"),
            causal_type="JOIN",
            worker_id="coordinator",
            logical_clock=3,
            payload=f"Merged={worker_results['worker_a'] + worker_results['worker_b']}",
        )
        physical_events_list.append(join_event)

        return ParallelDAGState(
            stage="DONE",
            delay_a=state.delay_a,
            delay_b=state.delay_b,
            events=tuple(physical_events_list),
            spans=tuple(spans_list),
            merged_result=join_event.payload,
        )

    def terminal(self, state: ParallelDAGState) -> bool:
        return state.stage == "DONE"


def canonicalize_dag_events(events: Tuple[CausalEvent, ...]) -> List[CausalEvent]:
    """Pipeline: Physical Event Log -> Canonical Sort by (logical_clock, event_id)."""
    return sorted(
        events,
        key=lambda e: (
            e.logical_clock,
            e.event_id,
            sorted(e.parent_event_ids),
            e.causal_type,
        ),
    )


def build_canonical_dag_hash(events: Tuple[CausalEvent, ...]) -> str:
    """Computes deterministic hash over canonicalized DAG including causal logical_clock."""
    canonical_events = canonicalize_dag_events(events)
    dag_repr = "|".join(
        f"clock={e.logical_clock}:id={e.event_id}:parents={','.join(sorted(e.parent_event_ids))}:type={e.causal_type}:worker={e.worker_id}:payload={e.payload}"
        for e in canonical_events
    )
    return hashlib.sha256(dag_repr.encode("utf-8")).hexdigest()
