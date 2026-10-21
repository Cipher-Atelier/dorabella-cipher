# TS-RECOVERED-SEARCH-v3 — единственная попытка 18.10.2026

Результат: **INCOMPLETE_BUDGET**, supervisor exit 2. Запуск 15:42:41.244121 UTC, release 15:42:42.367715 UTC, результат закрыт 15:43:23.621558 UTC. Elapsed до результата 42.393715372 с, до seal 42.409421220 с. Повтора нет.

Фактическая версия — v3: FREEZE `84146a52c5f0e2e53974c0220eb3cb63f698fd81c6250a522083099447050874`, MANIFEST `06414f0381afd15d6cf0ddae768323575836e1f98010fb061ce3c5d07d1523db`, исходный ZIP `7ad43c0ae2e3129f914bc090b7a521ddd24351b6dacd1b85361e757e24f53968`. Поле result.version=`TS-RECOVERED-SEARCH-v2` сохранено буквально как заранее известная legacy-метка runner; командная строка, FREEZE, launch receipt и пути удостоверяют v3. Исторический v2 STOP и его файлы не изменены.

## Фактическая работа и границы

- Одна blind-попытка Lincoln→Bedell87; Dorabella и дополнительные контроли не запускались.
- Исходная initialization завершена. Началась Expansion 1; законченных Expansion **0**. Score-записей и distinct scored strings **0**, LM requests/lookups **0**.
- Штатного best/final plaintext нет. Recovery и inverse этой попытки **не установлены**, а не равны неуспеху/false. Исходный ключ initialization `etaoinsrhldcpumf` — начальное состояние, не найденный ответ.
- Приняты ровно **200000 membership**; journal: 200003 полных записи = 200000 word + 2 list + 1 meta. Broker получил запрос ordinal 200004 и до его обработки поднял `INCOMPLETE_BUDGET_MEMBERSHIP` (runtime/broker.py:53). Последняя принятая запись имеет ordinal 200003. Это согласуется с terminal и stderr; намеренно отклонённый запрос не выдаётся за принятую запись.
- Pat list: 925 прочитанных кандидатов, 2 list calls, 1 cache hit/1 miss. Сортированный массив high-water 925. Последний записанный segmentation-progress — calls147, top4, maxdepth13; это неполный снимок, не конечное число вызовов.
- Broker exit1; Perl exit255 с `BRIDGE_EOF_OR_READ` после прекращения broker. Обе группы пусты, `verified_termination=true`. Дополнительное чтение /proc подтвердило отсутствие прежних PID3056/3057; никаких чужих процессов не останавливали.

## Ресурсы и лимиты

Неизменные лимиты: 180с total / 130с work, максимум3 процесса, AS128/128/256MiB, scores1024, LMrequests2049, lookups794624, membership200000, audit96MiB и каждый файл≤8MiB. До запуска memory.current4524339200B <5468942336B; все внешние identities и109 manifest-файлов совпали. Supervisor фактически прошёл staged AS soft128/hard256 и окончательный128/128; children получили прежние caps. Исправление порядка setrlimit позволило release без изменения вычислительных bytes.

375 наблюдений процессов: максимальный наблюдавшийся cgroup.current4562579456B; это выборочный максимум, не гарантированный полный пик. Broker наблюдаемые VmPeak39900KiB/VmHWM14500KiB (его terminal ru_maxrss14712KiB), Perl VmPeak17620KiB/VmHWM13088KiB. Supervisor ru_maxrss14712KiB. VmPeak/AS не RSS и не cgroup. CPU supervisor4.831965794с; children user35.740532с+system4.760546с. Остановка обусловлена membership-cap; исчерпания180с или OOM не зафиксировано.

## Evidence

raw_execution_receipt.json содержит точные четыре ответа exec/write_stdin единственной session96749, observed exit2 и первичный stdout с CLOSED_FILES_COMPUTED/SEAL_COMPUTED_SHA256. SHA receipt `58b3674775152082b77dde7154193cfab877635c1165fd75061ba87a573dd3d1`; seal `6d4e40984bd3f92fd57c17d6373fde95f2b9eeca64847cb1f7b3f7aca47c7004`; result `6420a5e28643274cb625f43639770b89949303bb28179d7dce8bc153edd27176`.

Локальный независимый data-only readback проверил17 закрытых файлов, hash/size/dev/inode/mtime, совпадение seal с первичным stdout,109 неизменных manifest-файлов и полные JSONL-записи. Общий размер attempt с seal18220872B. Итог доставки точной Library-копии фиксируется отдельно после сохранения ZIP; текущий документ не объявляет delivery PASS заранее.

Неполная первая Expansion ничего не устанавливает о recovery/чувствительности метода. Следующий запуск или изменение бюджета этим результатом не разрешены. Старые STOP остаются STOP.
