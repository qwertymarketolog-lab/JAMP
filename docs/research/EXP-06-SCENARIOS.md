# EXP-06-SCENARIOS: Parallel Frontier Test Scenarios and Workload Definition

**Status:** FROZEN  
**Target Spec:** `docs/research/EXP-06-SPEC.md`  
**Core Blob SHA-1:** `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`  

---

## 1. Топология сценария ($P \to WA, WB \to M$)

```text
                ┌────────────────┐
                │   Parent (P)   │
                └───────┬────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
   ┌─────────────┐             ┌─────────────┐
   │  Worker A   │             │  Worker B   │
   │    (WA)     │             │    (WB)     │
   └──────┬──────┘             └──────┬──────┘
          │                           │
          └─────────────┬─────────────┘
                        ▼
                ┌────────────────┐
                │   Merge (M)    │
                └────────────────┘
```

---

## 2. Сценарии верификации

### SCN-06-01: Concurrency Execution Span Overlap

- **Проверка:** Временные интервалы выполнения $WA$ и $WB$ перекрываются: $\text{Span}(WA) \cap \text{Span}(WB) \neq \emptyset$.
- **Критерий:** Подтверждена одновременность исполнения в независимых контекстах OS.

### SCN-06-02: Anti-Fake Concurrency Guard

- **Проверка:** Исключение последовательного цикла `for w in workers: w.run()`.
- **Дополнительная метрика:** $T_{\text{total}} < T(WA) + T(WB) - \epsilon$ (с учетом погрешности CI/GIL).

### SCN-06-03: Canonical Lineage Replay

- **Проверка:** Прогон 1 ($WA \to WB$) и Прогон 2 ($WB \to WA$).
- **Критерий:**
  1. $H(\text{CanonicalDAG}_1) == H(\text{CanonicalDAG}_2)$.
  2. Логическое состояние $M_1 \equiv M_2$.

### SCN-06-04: Core Immutability Gate

- **Проверка:** `git hash-object src/jamp/run.py` $\equiv$ `0fee0e1c5c1a1548361965ac51eacdeba62bfe8`.

---

## 3. Канонический причинный провенанс

Физический журнал `State.events` может отражать различный порядок прибытия результатов. Для Replay из него извлекается нормализованный `CanonicalDAG`; физический порядок не является частью критерия воспроизводимости.

---

## 4. Порядок заморозки перед стартом реализации

1. Записать `docs/research/EXP-06-SPEC.md` и `docs/research/EXP-06-SCENARIOS.md` в ветку `main`.
2. Зафиксировать коммит фиксации спецификаций и их хэши.
3. Ответвить `feature/exp-06-parallel-frontier` и начать разработку адаптера и тестового сюита строго по замороженным документам.
