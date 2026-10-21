# ARTIFACT-INTEGRITY-PROBE-v1 — prospective, не исполнен

Цель: один минимальный собственный тест локального write/read/hash/receipt пути с contemporaneous hash в raw stdout. Это не воспроизведение TS-JOURNAL, не попытка объяснить старую причину и не научный gate.

## Единственные данные

Literal ASCII bytes, без BOM/CRLF/пробелов, ровно 48 байт:

```python
b'{"i":0,"v":"A"}\n{"i":1,"v":"B"}\n{"i":2,"v":"C"}\n'
```

Положительный файл `payload.jsonl` — эти байты. Отрицательная копия `altered.jsonl` — те же 48 байт, единственное изменение offset **12** (0-based) `A` → `D`. Это fixture повреждения, не допустимый альтернативный результат. Никаких случайностей, seeds или других входов. Все операции только внутри нового пустого каталога; существующий каталог означает REFUSE, а не resume.

## Единственный конечный вызов

Перед будущим запуском freeze собственного runner и manifest. Обычный Python stdlib; ни один TS module/source не импортируется. Не более одного дочернего вызова существующего `/usr/bin/sha256sum -- payload.jsonl altered.jsonl`; stdin DEVNULL, captured stdout/stderr, child timeout 2 s; без shell. До exec фиксируются идентичность выбранного Python и sha256sum. Максимум два процесса одновременно, каждому AS64 MiB, CPU5/6 s, files <=64 KiB каждый, суммарный output <=256 KiB. Кооперативный общий deadline 10 s; это не realtime hard-kill или host-crash durability. Нет очереди, фоновых jobs, retry или восстановления таймера.

1. Создать оба fixture через exclusive binary open. Для payload написать ровно три заранее заданные строки, проверить write counts, flush и close. Для него сохранить dev/inode/path, размер, monotonic времена; после close прочитать весь файл через отдельный readonly fd, до EOF, сравнить bytes с literal в памяти. Никакого открытия исходных исследовательских артефактов.
2. Один вызов GNU sha256sum над двумя файлами. До записи result вывести в stdout один JSON receipt, включающий exact expected bytes hex, writer-intent/closed-reader hashes, оба **сырых** GNU вывода/exit, bytes/identities/timestamps и проверку отрицательного fixture. Stdout немедленно flush; stdout receipt — отдельное свидетельство tool call, не только текст будущего result.
3. Сохранить ровно эту структуру в result JSON, закрыть и заново прочитать; сравнить разобранную структуру с той, которую вывели. Создать один малый ZIP с payload/result и прочитать его члены как данные. Финальный stdout содержит hashes result и ZIP. Снаружи после exit — один data-only readback по сохранённому raw tool output: все буквально напечатанные hashes/fields должны совпасть с файлами и членами ZIP. Без повторного исполнения runner.

## Предварительно фиксированный критерий

`PASS_LOCAL_ARTIFACT_ONLY` допустим только при exit0 исходного вызова, закрытых процессах, отсутствии stderr/исключений/timeout, времени <=10 s, точных 48/48 bytes, согласии собственного SHA256 с GNU и byte equality оригинала, **отклонении altered как mismatch**, совпадении raw stdout receipt/result/readback/ZIP. Полный учёт обоих fixtures обязателен. Несогласие — STOP; потеря наблюдения/terminal evidence — UNKNOWN. Не исправлять код или fixtures после исхода и не повторять в этой версии.

Тест не включает network/Library transfer в свой исполняемый scope; обычное сохранение законченного artifact — после завершения. Уже подтверждённое в provenance-чеке совпадение архивных копий не тестируется снова. Он не докажет причину исторического сбоя, полную честность среды, durability, эквивалентность численного solver, чувствительность или расшифровку. Сейчас сохранён **только план**, runnable code ещё не создавался и не исполнялся.
