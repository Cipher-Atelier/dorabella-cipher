# Следующий минимальный оригинальный oracle — НЕ запускался

Назначение: оригинальные Utils::ReadPList/NoSpace::FindWords как внешний oracle для
нынешнего API, без MCTS, ReadLM/JMSmoothing, численных моделей или target.
Это проверит Perl string/list/lexicon/segmentation на двух фиксированных fixtures;
даже PASS не докажет numerical equivalence scorer или search trajectory.

Исполняемый harness `original_module_oracle.pl` готов. Импортируются ровно два
неизменённых авторских модуля pinned commit и core JSON::PP. Оригиналы не патчатся.
Один процесс, две пары аргументов: маленький golden fixture и source subset из
прошедшего собственного теста. Последний содержит полный order-1 словарь, все
элементы семи фиксированных запросов и исходный maxlen; это не поиск.
Harness выводит полные списки/словарь/сегментацию, сверяет canonical JSON побайтно,
при первой разнице die; normal exit0 требуется вместе с обоими результатами.

Ранее пользователь разрешил исполнение этого оригинального пакета для ограниченных
контролей. Авторизация неизменённых Utils.pm/NoSpace.pm сохраняется; нового согласия
на сами эти исходники не требуется. Текущий ответ намеренно ограничен собственным
adapter/reference; команда ниже подготовлена для отдельного readback/запуска, не
выполнена. Та авторизация НЕ распространяется автоматически на новый Perl glue,
изменённую строку106 MCTS или broker-процесс: для их исполнения нужен отдельный
конкретный freeze и подтверждение модифицированной связки. Нынешний harness не
заменяет solver переписанным вариантом и не обходит это ограничение.

Предусмотренная следующая стадия: один вызов, общий wall30с включая загрузку двух
модулей/fixtures, TERM затем KILL через2с, AS512MiB,CPU25/28с,core0,nofile64,
stdout/stderr≤16MiB. Сначала fresh cgroup gate8GiB/current≤7GiB, проверка всех SHA,
отсутствие attempt/live процесса; никакой fullmodel load. При новом runtime mismatch,
разнице, нехватке ресурса или неясном terminal — STOP/UNKNOWN, не retry.
Границы timeout не обещают realtime hardkill; наблюдать этот же процесс, сохранить
exit/process-group evidence штатным supervisor с уже исправленной PID/NSpid логикой.
Не переносить старый TS-RC runner, который автоматически запустит MCTS.

Точная payload-команда после этих preflight (пути абсолютные):

```sh
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PERL_HASH_SEED=2026101705 PERL_PERTURB_KEYS=0 \
  /usr/bin/timeout --signal=TERM --kill-after=2s 30s \
  /usr/bin/prlimit --as=536870912:536870912 --cpu=25:28 --core=0:0 --nofile=64:64 --fsize=16777216:16777216 -- \
  /usr/bin/perl -I /workspace/scratch/f24f8fae4976/TREESEARCH_feasibility_20261017/original \
  /workspace/scratch/f24f8fae4976/TS_ADAPTER_CONTRACT_v1/original_module_oracle.pl \
  /workspace/scratch/f24f8fae4976/TS_ADAPTER_CONTRACT_v1/attempt/fixture/fixture.patlst \
  /workspace/scratch/f24f8fae4976/TS_ADAPTER_CONTRACT_v1/attempt/golden_oracle_expected.json \
  /workspace/scratch/f24f8fae4976/TS_ADAPTER_CONTRACT_v1/attempt/oracle_fixture.patlst \
  /workspace/scratch/f24f8fae4976/TS_ADAPTER_CONTRACT_v1/attempt/oracle_expected.json
```

Не считать stdout cap обеспеченным одним RLIMIT_FSIZE при pipe: будущий supervisor
должен считать bytes/направить в ограниченные regular files. Дочерних jobs harness
не создаёт; внешние date/system/backticks исходного MCTS отсутствуют, он не импортируется.
Все input hashes для этой команды будут сохранены в NEXT_ORACLE_INPUTS.json после
успеха, без запуска. Runtime/timeout/prlimit identities также фиксируются чтением.

После этого нужен отдельно подготовленный native bridge с тем же API; вариант
с Python SQLite broker не требует установки DBI, но добавляет IPC/дочерний процесс.
До его freeze, дифференциальной проверки и safe bound для LM+поиска full solver
и Dorabella остаются вне допуска. В этом документе не предлагается новый scorer.
