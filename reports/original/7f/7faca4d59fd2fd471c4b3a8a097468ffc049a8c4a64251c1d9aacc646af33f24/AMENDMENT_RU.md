# TS-ADAPTER-CONTRACT-v2

Единственное функциональное изменение к frozen v1: uri=True при открытии SQLite URI.
Остальные входы/семантика/fixtures/критерии и лимиты180с/256MiB неизменны.
run_contract.py меняет только label версии. PLAN_RU.md — побайтовая копия принятого
v1 плана, применяемая к отдельному v2 attempt с новым инженерным T0; v1 STOP неизменен.
Одна попытка v2; при ошибке STOP без повторов. Никаких дополнительных проб adapter.

При PASS/readback возможен один отдельный заранее frozen original-module differential
по текущему прямому разрешению пользователя: два fixtures, только неизменённые
Utils/NoSpace, точное равенство массивов/дублей/словаря/maxlen/сегментации, tolerance=0.
Не scorer и не полная numerical equivalence. Дальнейший stage freeze отдельно
после готовности входов; без модифицированного solver/glue.
