# ARTIFACT-INTEGRITY-PROBE-v1 — результат единственной попытки

**PASS_LOCAL_ARTIFACT_ONLY.** 18 октября 2026 года выполнен один собственный data-only тест. Runner и GNU sha256sum завершились с exit 0; независимый readback — с exit 0. Повтора не было.

Тест касается только этих новых файлов. Он не объясняет историческое поле `75236ae0…` в TS-JOURNAL-DIAGNOSTIC-v1 и не меняет прежние STOP.

## Что было зафиксировано до запуска

Три ASCII-строки, каждая с завершающим LF, без BOM/CRLF, всего ровно 48 байт:

```jsonl
{"i":0,"v":"A"}
{"i":1,"v":"B"}
{"i":2,"v":"C"}
```

Отрицательная копия: ровно одна замена по **0-based offset 12**, `A` (41 hex) → `D` (44 hex). Все остальные байты идентичны.

Freeze SHA256: `66e6088dfb92e0c147469ffb4828349d88c8b0a1142956ada26fbc8a9dfd7d77`.
Runner SHA256: `d8c581018d4a63930b05bd0b1caa8f5d6feec6b67159a5c11a7b98c8ac16cd7a`.
Readback SHA256: `536131d68475779a4c09bb7f04e3ed5357c504d6aa197cadf45be7ae3a12290e`.

Критерий: точные bytes, совпадение Python hashlib и GNU sha256sum, отклонение отрицательной копии, первичный stdout до записи result, побайтовое соответствие stdout/result/ZIP, нормальный exit и независимый readback. Любое расхождение — STOP без повтора.

## Фактическое выполнение и первичные свидетельства

Команда:
```
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -B -I -S /workspace/scratch/f24f8fae4976/ARTIFACT_INTEGRITY_PROBE_v1_package/runner.py
```

Исходный ответ инструмента: chunk `a28335`, exit 0, без session ID. Он целиком сохранён в `RAW_TOOL_RECEIPT.json`, включая обе строки stdout. Внешние UTC-границы вызова: **12:12:35.942–12:12:36.477**, интервал 0,535 с; это время наблюдения вызова, не время CPU. Собственный монотонный elapsed runner: **0,047744938 с**. Поле инструмента wall_time_seconds 0,000030957 также сохранено без переинтерпретации; оно не заменяет измерение runner.

Последовательность: три записи по 16 байт → flush → close → чтение через новый fd → Python SHA256 → один GNU sha256sum для двух файлов → немедленный stdout с HASH_RECEIPT → запись result.json → ZIP/readback → TERMINAL. Порядок отражён монотонными метками. Dev/inode/размеры записывающего и читающего fd сохранены; размер положительного файла последовательно 16/32/48 байт.

GNU child exit 0, stderr пуст, child reaped=true. Его собственный наблюдаемый интервал 0,001643 с. Пиковый ru_maxrss: runner **13696 KiB**, child **13696 KiB**; это показания API, не суммарный пик всей среды и не гарантия RSS каждого момента. Применены AS 64 MiB каждому, CPU 5/6 с, FSIZE 64 KiB, NOFILE 32, CORE 0; не более двух процессов, один GNU-вызов. Плановый общий предел 10 с кооперативный, child timeout 2 с. Нет обещания realtime hard-kill, cgroup-reservation или долговечности после host-crash.

## Хеши и независимый readback

| Артефакт | SHA256 |
|---|---|
| payload.jsonl, 48 B | `fc19016a6a6b953ee2853e0642e11d19096a3f9f2a6f9c8698c9c4be9fd74935` |
| altered.jsonl, 48 B | `4caedbc23e7d2670413bd3a81397953327f8c0f9468d9b254b3793e9deb63c8f` |
| result.json | `06340c80ce5322b2a268163dd2e9a421340a66ab5bbb5cd331ae1e52c454c3c1` |
| внутренний artifact.zip | `865b0090df0c4b0e69b27b8bd2c84a79d7ed6e6731f48c795dab27cba1cbfec2` |
| весь первичный stdout | `36bc8123df727314de934ae5ddbbf7a7118c5633a7d5387cde646b5354292a6d` |

Python hashlib и отдельный установленный GNU sha256sum совпали для обеих копий. Отрицательная копия отвергнута; единственное различие — offset 12. Это независимые средства хеширования, но они читают одну файловую систему и не являются независимыми хранилищами.

Отдельный заранее frozen `readback.py` только прочитал данные; runner и математические/криптоаналитические процедуры не запускал. Он сверил две полные строки tool-observed stdout с result.json и terminal.json, все семь terminal hashes, exact bytes и отрицательную мутацию, порядок write/close/hash/emit, GNU exit, собственные code hashes и точные три члена ZIP. Итог `READBACK.json`: PASS_LOCAL_ARTIFACT_ONLY, elapsed 0,001146292 с. Его фактический tool-output сохранён отдельно; chunk `eddc7c`, exit 0.

## Предел вывода

Установлена целостность этой новой 48-байтовой попытки, включая непосредственную фиксацию хешей в stdout до result. Это не воспроизведение старой неисправности и не доказательство общей надёжности артефактов, больших IPC-журналов или старого seal. Сторонний код, broker/Perl/solver, сеть, исходные модели и прежние научные артефакты тестом не затрагивались.

Полный пакет содержит неизменные freeze/код/принятый план, первичный receipt, файлы попытки и readback. MANIFEST.json задаёт размеры и SHA256 каждого члена (кроме самого manifest); SHA256SUMS.txt относится к итоговым файлам доставки.

