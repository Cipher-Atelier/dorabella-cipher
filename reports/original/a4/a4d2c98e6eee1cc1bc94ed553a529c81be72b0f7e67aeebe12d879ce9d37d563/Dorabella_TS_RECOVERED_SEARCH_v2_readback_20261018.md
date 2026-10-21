# TS-RECOVERED-SEARCH-v2 — подготовлено, не исполнено

Новая восстановленная версия, **не утраченный freeze**. Старые STOP неизменны. Все14 модельных входов с точными hashes восстановлены; индексы не перестроены. Собственный каталог восстановлен один раз: **7548932 строки →682961 элементов,6221764 байта**, SHA256 `8e29af726d88e0c2e711e03ab4019a3b0666fb0d4184302080edd6733013e76e` совпал. Exit0,8.849013с, RSS31104KiB. Новый Perl/broker/glue не импортировался, не компилировался и не исполнялся.

Входы/protocol, каталог и промежуточный код сохранены отдельными checkpoint до завершения подготовки. Их идентификаторы и hashes — в CHECKPOINT_DELIVERY.json. Финальный архив содержит код, source diffs, исходные модули, контроль/отдельную истину, каталог, budgets, статический review и явную relocation14 данных. Большие уже сохранённые модели/индексы не дублируются; exact paths/hashes и ссылки для восстановления включены.

## Следующее единственное действие для согласования

Реальный blind поиск **Lincoln→Bedell87**, исходная initialization, две штатные Expansion и одновременный profiling. `-n -v -mi 2 -pc 1 -pl 50 -cc 0.05`; прежние key/hash seed/scorer неизменны. CLI-разделители исправлены по сохранённому PLAN_MANIFEST до исполнения; ранний checkpoint остаётся промежуточным.

```bash
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -B -I -S /workspace/scratch/f24f8fae4976/TS_RECOVERED_SEARCH_v2/runtime/launch.py
```

180с total от T0, cutoff работы130с; максимум3 процесса, AS128/128/256MiB,512MiB суммарно;1024 scores,2049 LM requests,794624 lookups,200000 membership. Audit96MiB, файлы≤8MiB. Никаких target, повторов, изменения caps или настроек. Конечность caps не гарантирует завершение Expansion; **INCOMPLETE_BUDGET допустим**, включая остановку до первого score. Recovery оценивается отдельно от87/87 inverse, только штатный best завершённой итерации. Полное завершение двух итераций само по себе не доказывает чувствительность.

Memory snapshot **2026-10-18T14:40:06.319466+00:00**: current=4492333056B; max=8GiB. Порог новой полной формулы current<5468942336B, **PASS_SNAPSHOT_ONLY**; input pages=1376161792B. Cache не вычитался, резерв1GiB сохранён. Перед execution — свежие resource/process/hash gates; shared race и отсутствие realtime/host-crash гарантий явно описаны. Нового attempt/T0 нет.

39 статических проверок. Вычислительный хвост MCTS побайтно совпал с оригиналом после удаления observer-строк; арифметические/сегментационные модули неизменны. Это не runtime-proof нового glue. Прямое независимое сравнение всех list frames/элементов с каталогом + ordered references + полный LM raw заменяет повторный payload-журнал, **не сами FETCH**. Final acceptance требует closed files → raw tool computed hashes → точный ZIP readback; простой hash без сравнений не используется как замена.

## Идентичности

- ZIP SHA256: `5b97698dd667a290a0cb62844a790376d839b19c47f673d9ec1cb5facd527817`
- FREEZE SHA256: `c12035b1494d3c2acc8a3b17abcd1208c30c2758d8481013cc3c4eff445d07b5`
- MANIFEST SHA256: `4df5dbe4883ca4c8ee36513058472955f6d0b340874093b920afcf515b6f595e`

| Подготовленный файл | SHA256 |
|---|---|
| `launch.py` | `cccc03c69c6181973b18bc6bb3b837702fe2624a9c84a62d1c995cd23f684f9f` |
| `run_profile.py` | `cac153de6b3ce96cff53aea08897f6baf3120acfda4ae4a7e89c938d6d7e233e` |
| `child_gate.py` | `911bc7d0dba75629eac5b6c73e8ba85a38c7e4c88130056422c6693dbec578b1` |
| `broker.py` | `0ffcc60b5618071f43c1961fc3a8d60f28a71dcc6120165b23db5a1e1f73e384` |
| `profile.pl` | `ea96b1cab25f27e6fe3af5cbe463bcfeba9fab119dd2ebc8e56826a81a514d3e` |
| `Observe.pm` | `e19b9ad3de0752ea1faa0b157f22db49e603ad60842e6b53da8469674d832e32` |
| `StreamAudit.pm` | `20a4973b4b8c3ba9b8e3fc8a7f17d54b3b6b54af1949fefb2a576d4d709e893a` |
| `readback.py` | `cc51c56382d113e3b436ed6772d87b951a04d4474cacf8a4505eb6e1fa18dfca` |
| `verify_delivery.py` | `cef573f3ace0b14d4c38f3e90c8f48169dbb901a74ee2d7bf6a98c4e551b380c` |

Полные критерии и ограничения — README_RU.md, PROTOCOL.json, BOUNDS.json, STATIC_REVIEW.json. Новое исполнение ожидает readback/согласования; этот документ его не запускает.
