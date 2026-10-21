# TS-COMBINED-STORAGE-v1 — готовый пакет, исполнение NO_GO

Подготовлен один совместный broker patlst+LM с **двумя отдельными pipe-каналами**. Это позволяет оставить `Prefetch.pm` и `CompactPatList.pm` побайтно неизменными и не увеличивать число процессов. Их счётчики запросов, буферы и close не смешиваются. Оригинальные ReadLM/JMSmoothing/Utils/NoSpace и вычислительные тела MCTS сохранены; новые broker/harness/supervisor подготовлены, **не исполнены**. Perl не запускался даже compile-only.

Собственный pure-contract test: **37/37**, AST12, exit0, 0.015968323 с, RSS12356 KiB; без импорта broker/adapter, IPC или модели. Это проверка собственных форматов/границ/состояний, не численной эквивалентности. Статическая сверка:19/19 assertions. Источники, конкретные изменения, negative fixtures и raw preparation receipt включены.

## Один конечный следующий gate

После отдельного согласования — одна попытка, без retry/resume:

1. Полные identities и **gate всех входов до первого авторского процесса**; при отказе `NO_GO_BEFORE_FOREIGN`, без запуска маленькой части ради частичного PASS.
2. Один reference и combined adapted: прежние3×2 synthetic MCTS, все320 trace events/score bits/segmentation/ties, 118×6 inverse на сторону. Повтор обусловлен новой одновременной работой обоих storage APIs; закрытые standalone этапы не предлагаются заново.
3. Только при exact PASS и свежем gate — один совместный transport:6244 прежних LM lookup,8 patlst fetch (132856 candidate occurrences, полный порядок/дубли),6 прежних коротких NoSpace примеров с35 membership queries. Между запросами к двум реальным хранилищам чередование; scorer/search на реальных данных отсутствуют. Сохраняются все списки/ответы, не sample.
4. Хеши после чтения, полный accounting, нормальные exits и terminal evidence. `PASS_FINITE_COMBINED_STORAGE_ONLY` — только конечное интеграционное свидетельство; до87-control и target автоматического перехода нет.

Общий180 с; максимум3×AS64MiB, NOFILE64, CPU45/50 с на ребёнка, output8MiB/file,32MiB total; TERM/KILL только собственным подтверждённым группам. Два IPC канала остаются в одном broker, без новых jobs. Real phase≤60 с; её probe≤30 с, из них накопленное измеренное LM IPC≤10 с. Последнее — явно новый combined timing contract, не подмена standalone wallclock. Realtime timeout и host-crash durability не обещаются.

## Ресурсный freeze: NO_GO

Снимок **2026-10-18T00:42:16.455538+00:00**, только одно чтение current для этого freeze:

| Состав | Байты |
|---|---:|
| Малые source/runtime files +1MiB metadata | 38,223,872 |
| Шесть LM +шесть индексов +patlst +SQLite | 1,331,834,880 |
| **Все input pages** | **1,370,058,752** |
| Сумма AS caps / IO-kernel-output allowance | 201326592 /67108864 |
| Наблюдавшийся memory.current | 6,810,947,584 |
| Проекция / строгая граница | 8,449,441,792 /7516192768 |
| Необходимое current **строго ниже** | **5,877,698,560** |

Недопуск **933,249,024 B**. Сохраняются cgroup8GiB, граница7GiB и номинальный резерв1GiB. Cache/slab не вычитаются, reclaim не предполагается. Никакие данные не удалялись, настройки не менялись, сигналы процессам не посылались. Нельзя переносить старые491106304 B на объединённый пакет: добавились production patlst+SQLite и собственный код/fixtures. Подробный пофайловый расчёт — RESOURCE_BUDGET.json.

Pat cache≤2 lists/8MiB учтённых объектов, words≤1024; SQLite cache setting4MiB (не hard bound всей SQLite). LM cache4096 entries/raw payload≤1966080 B; крупнейший список63911 элементов/raw payload≤2939906 B. Есть временные копии/JSON/Perl objects сверх payload. Frame≤65536 B; два receive buffers≤131072 B. **Полный совместный peak и достаточность AS64MiB не измерены**: превышение даст STOP, не увеличение cap. Порядок/дубли не урезаются. Patternlimit50 не ограничивает чтение и сортировку всего candidate list.

## Что готово и что осталось

Код, diff, source provenance, конечный план, fixtures, resource formula и readback готовы для рассмотрения. Единственный текущий подтверждённый ресурсный blocker — приведённый gate. Это не отрицательный научный результат и не исчерпание исследования.

После полного интеграционного PASS останется отдельный bounded entrypoint технического87-control с original frequency initialization и проверкой87/87; его search peak/throughput и чувствительность здесь не установлены. Ни87-control, ни полный solver/target не входят в новый пакет. Связанные шаги не дробятся на отдельные разрешения для каждой внутренней функции.

Будущая команда (сейчас **не выполнять**):

`/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -B -I -S /workspace/scratch/f24f8fae4976/TS_COMBINED_STORAGE_v1/launch.py`

FREEZE SHA256 `33c953e9982803aa5fe9b6bffce9d43d8b55ac43052a73604ef9211d1adc8a0a`. `T0=null`, attempt отсутствует, allowed stages до согласования пусты. Все запускаемые файлы и14 больших data identities закреплены в FREEZE; большие файлы сейчас проверены по наличию/размеру и прежним hashes, их содержимое повторно не читалось. Они не дублируются в ZIP; будущий launcher обязательно проверяет hashes перед использованием.

Исходные компоненты: commit `2c7ad49cd4f4fa852168a8ce295bf739bf076adc`; parent LM FREEZE `7009da08780275e7a917e6712098294f87035a40cceeb65fe2a388fb20ec6d86`; parent pat FREEZE `ac6f8d99cb78f414b1b0f825c2da79ae25288557a888df35fd338099fa197d98`. Старые артефакты неизменны.
