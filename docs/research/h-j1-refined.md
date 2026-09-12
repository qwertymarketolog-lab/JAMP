# H-J1 refined: branch-scoped substitution convergence

Scope: root=2, source p = 2·k_6, vocabulary @ d1b3a8c
Method: code reading only, no execution

## Claim

Substitution-layer имеет единственный fixpoint независимо от порядка применения novel-пар, для указанного scope.

## Derivation

- 1 source × 4 targets
- четыре substitution-результата попарно различны (проверено по canon())
- ни один результат не является source-shaped (ни equality с var слева, ни иным source-предикатом)
- следовательно: source pool стабилен, target pool стабилен
- novelty-фильтр монотонно исчерпывает 4 пары, fixpoint уникален и независим от порядка

## Applicability boundaries

- не устанавливает общего случая (любой root, любой source)
- не устанавливает расширенного R_test characterization
- не устанавливает C1/C2 как теорем (это H-J2 partial, M-008)
- не является execution evidence; получено чтением кода

## What this gives

H-J1 refined служит частным случаем и базовым результатом для H-J2: общей характеризации класса систем, в которых substitution-layer имеет единственный fixpoint независимо от порядка.

## Evidence chain

Source code:    track_a/common.py @ d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39
                blob d0956421f54e76a89f4a845e306f30f7b1d3c8e8
Method:         static reading
Related:        M-013 (this finding)
                M-008 (H-J2 partial)
Prior work:     S0+ = 9 (commit d7e28e6)
                30-run reproduction (commit 4f5bbc47)
Evidence level after this document: repository-artifact
