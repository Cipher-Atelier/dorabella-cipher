# TS-RECOVERED-SEARCH-v2 — результат единственной попытки

18.10.2026. Итог: **STOP_CORRECTNESS**, observed exit 2. Старые результаты и frozen ZIP не менялись; повтор не выполнялся.

## Фактический запуск и работа
- Точный launch: 15:10:06.792427 UTC; result end 15:10:07.940667 UTC; seal 15:10:07.942460 UTC.
- Elapsed до result 1.162002715 с; до seal 1.163820623 с. Ограничения 130/180 с не исчерпаны.
- Внешняя предварительная проверка: 120 уникальных файлов совпали с identities, прежней попытки и совпадающих процессов не найдено.
- Memory admission прошёл: внешний snapshot 4493746176 B; supervisor before 4496715776 B и after_hashes 4496920576 B; порог строго <5468942336 B, memory.max 8589934592 B.
- Запущены две Python child-gate оболочки; foreign_released=false. Авторский Perl и новый broker не исполнялись; SEARCH_RELEASED отсутствует.
- Завершённых Expansion: **0**; scored records/distinct strings: **0/0**. Native best отсутствует. Recovery и inverse не оценивались — это не false recovery и не отрицательный результат метода.
- Native status STOP_CORRECTNESS / STOP_BEFORE_READY:perl. Не бюджетный исход.
- Supervisor CPU 1.108262338 с, maxrss 14676 KiB. Children aggregate rusage: user 0.029437 с, system 0.020678 с, ru_maxrss 14676 KiB. Это не замер peak полноценного solver и не сумма RSS.
- Broker-gate завершён SIGTERM (exit -15), Perl-role gate exit 1. Обе process groups пусты, wait выполнен. Отдельное последующее чтение /proc не нашло наблюдаемых совпадений сохранённого namespace или точного child_gate script. Недоступные namespace-read перечислены отдельно в independent_local_readback.json; они не заменяются догадкой. Совпадение namespace inode само по себе не использовано как идентичность: новые tool-процессы имели тот же namespace inode, но другие PID/starttime. Первичная терминальность основана на wait и пустых группах supervisor; дополнительная проверка использует точные PID/starttime и script argv.

## Доказанная причина
runtime/run_profile.py:76 устанавливает supervisor RLIMIT_AS=(134217728,134217728), затем строка 41 создаёт дочерний процесс. Hard limit наследуется. runtime/child_gate.py:5 применяет лимиты роли; в FREEZE role_limits.perl RLIMIT_AS=(268435456,268435456). NOFILE/CORE/FSIZE перед ним равны у обеих ролей; именно AS — первая попытка повысить hard limit. Первичный stderr фиксирует ValueError: not allowed to raise maximum limit на этой строке.

Gate упал до ready-файла роли Perl и до чтения разрешающего G (child_gate.py:8–9), следовательно до execve broker/Perl (строки 11–15). Run_profile.py:93 ожидает оба ready и выдаёт G только в строке 97; до неё код не дошёл. Это конкретный дефект supervisor в порядке выставления наследуемых hard limits, а не OOM модели. Уже прошедший memory gate не устраняет эту ошибку.

Код в этой попытке не исправлялся. Возможный будущий проект исправления должен сохранять конечные AS 128/128/256 MiB, создавать Perl-role gate до необратимого снижения родительского hard AS и доказать установку всех конечных caps до release. Ни такого кода, ни новой попытки здесь нет.

## Evidence и границы
Первая собственная packaging/readback-команда остановилась при PermissionError чтения /proc/1/ns/pid; её сырой ответ сохранён отдельно. Это не новая попытка runner. Вторая packaging-команда остановилась из-за слишком широкого собственного критерия совпадения namespace; stdout отдельной data-only диагностики показал новые PID/starttime текущего tool, а не прежние процессы. Оба packaging failure сохранены. Итоговый data-only verifier сравнивает именно сохранённые PID/starttime и точный script argument; недоступные namespace reads перечислены. Frozen код не изменялся.
raw_execution_receipt.json содержит два полных объекта tool response одной session 88647, точную команду, stdout и exit. stdout непосредственно содержит CLOSED_FILES_COMPUTED и SEAL_COMPUTED_SHA256; это первичное наблюдение инструмента, а не восстановленный пересказ. Девять sealed файлов сверены по hash/size/dev/inode/mtime. Все 88 manifest members остались неизменными.

independent_local_readback.json — только чтение сохранённых данных и /proc, без solver/scorer. Его успешная проверка удостоверяет доставленные свидетельства STOP, не scientific PASS. Exact Library readback архива выполняется отдельно неизменённым runtime/verify_delivery.py; отдельная запись delivery_readback должна сопровождать архив.

В архив включены frozen code, sources/diffs/protocol, каталог, полный attempt, launch receipt, raw execution receipt, внешний preflight и этот отчёт. Большие 14 модельных inputs не дублируются: точные пути и hashes сохранены в model_inputs.json и внешней проверке.
