2026-11-02  Day 4: data layer done (player.yaml, seoyeon.yaml, schema, db.py, 5 tests pass). Next: judge prompt and text loop (Milestone 2).
2026-11-02  Day 5: LLM wrapper done (chat, chat_json, think=False default). think=True adds ~14s; think=False median 1.5s. chat_json 10/10 parse at ~3.4s median. Next: judge prompt.
2026-11-02  Day 6: character chat done. prompts/character.md, kotoba/character.py, kotoba/cli.py. Scripted 10-turn test passes: 해요체 throughout, short replies, no grammar corrections. Next: judge prompt + register scoring.
2026-11-02  Day 7: judge done. 40-row eval set (haeyo/banmal/hapsyo/honorific/grammar). Register accuracy 90% (36/40); offense P/R 90%/90%. Honorific rows 30-33 mislabeled due to model conflating register with honorific correctness — known issue, acceptable for now. llm.py: added $ref resolver for Ollama nested schemas. Next: wire judge into cli.py turn loop.
2026-11-12  Day 8: Korean ending validator done. validator_ko.py classify() scans words right-to-left for hapsyo/haeyo/banmal endings. Validator 100% (40/40). Judge integrates validator: high-confidence disagreements override register_used. eval_judge/eval_validator print summary only; full details to CSV. Next: wire judge into cli.py turn loop.

Later:
  - Judge misses honorific errors (4/4 Day 7 misses). Fix: honorific rule check + subject/verb fields. Deferred.
