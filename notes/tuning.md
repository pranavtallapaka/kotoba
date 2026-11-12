2026-11-02  Day 4: data layer done (player.yaml, seoyeon.yaml, schema, db.py, 5 tests pass). Next: judge prompt and text loop (Milestone 2).
2026-11-02  Day 5: LLM wrapper done (chat, chat_json, think=False default). think=True adds ~14s; think=False median 1.5s. chat_json 10/10 parse at ~3.4s median. Next: judge prompt.
2026-11-02  Day 6: character chat done. prompts/character.md, kotoba/character.py, kotoba/cli.py. Scripted 10-turn test passes: 해요체 throughout, short replies, no grammar corrections. Next: judge prompt + register scoring.
2026-11-02  Day 7: judge done. 40-row eval set (haeyo/banmal/hapsyo/honorific/grammar). Register accuracy 90% (36/40); offense P/R 90%/90%. Honorific rows 30-33 mislabeled due to model conflating register with honorific correctness — known issue, acceptable for now. llm.py: added $ref resolver for Ollama nested schemas. Next: wire judge into cli.py turn loop.
2026-11-12  Day 8: Korean ending validator done. validator_ko.py classify() scans words right-to-left for hapsyo/haeyo/banmal endings. Validator 100% (40/40). Judge integrates validator: high-confidence disagreements override register_used. eval_judge/eval_validator print summary only; full details to CSV. Next: wire judge into cli.py turn loop.
2026-11-12  Day 10: memory retrieval + session summaries. character.py: _select_memories() returns last-5 + keyword-matched older ones (Korean 2+ char and English 3+ char tokens). summaries.py: 3-paragraph English summary (relationship delta, slips, one fact) via LLM. cli.py: tracks session_slips/session_memories in-loop; /quit generates+stores summary. 2-session test: hometown (부산) stored from session 1, persists to session 2 prompt; summary correctly identifies no slips and the Busan fact. Summary LLM occasionally ignores slip list (stochastic); data is correct upstream. Next: TTS or episode beats.
2026-11-12  Day 9: consequences wired. state.py applies bounded deltas (closeness -3..+3, respect -10..+3), beginner tolerance (respect capped at -3 for slips; grammar-only = 0 cost), relationship_speed scales positive closeness. character.md behavior_note: cooler at respect<40, awkward beat at mild offense, repair demand at serious. explain_slip() shows one English line after register/honorific errors. /why command. 4-turn test: 3 polite + 1 반말 → respect 50→46, offense→mild, slip explanation fires. Stochastic honorific false-positives from judge still possible (preexisting issue). Next: TTS or episode beats.

2026-11-12  Day 11: 3 live sessions analysed (14 new turns). Findings and fix #1 applied.

  FINDINGS
  1. Judge inconsistencies
     - T15 CRITICAL false positive: "저도 같이 먹어도 돼요?" (clean haeyo) got register_match=True
       but banmal_before_offer fired because judge saw medial -어도. Caused -6 respect penalty,
       offense=mild, awkward beat — with no explanation shown to player (register_match was True
       so explain_slip stayed silent). Root cause: judge LLM ignores its own rule that
       banmal_before_offer requires register_used=="banmal".
     - T19 false honorific error: ['선배님'] listed as honorific_error — the player used the
       correct address term. Triggered misleading "[Slip] Honorific slip: 선배님." message.
     - T22 missed grammar error: "저는 어제 갈 거예요." (future+past adverb, row 35 of eval set)
       — judge gave +1/+1. Stochastic miss.
     - T17 vs T23: similar honorific errors got -4 and -1 respect deltas respectively.
       Judge sets its own delta without reliable anchoring to the prompt's -4 rule.

  2. Character reply issues
     - T16: "저도 잘 씨네요." — garbled Korean (failed generation).
     - T20: "네, 알겠습니다." — character used 하십시오체 form in a 해요체 session.
     - T24: Character echoed player's words back verbatim.

  3. Explanation lines
     - Accurate and helpful: T17, T18, T21, T23.
     - T15: silent false penalty — character offended, no explanation shown.
     - T19: incorrect — "Honorific slip: 선배님" for the correct address term.

  4. State speed
     - After 14 turns across 3 sessions: closeness=29 (threshold 60), respect=46 (threshold 55).
     - Need 31 more clean turns for closeness offer at +1/turn. Too slow.
     - Respect yo-yos around 44-54 due to asymmetric penalties.

  TOP 3 FIXES (ranked)
  #1 APPLIED — Code guard: strip banmal_before_offer when register_used != "banmal";
     also clear offense level and zero negative respect delta. (judge.py)
     Verification: "저도 같이 먹어도 돼요?" now returns offense=none; "고마워." still returns offense=mild.
  #2 APPLIED — Filter honorific_errors entries without → separator (judge.py).
     Drops bare address terms (선배님 etc.); stops false "[Slip] Honorific slip: 선배님" messages.
     Eval: register 100%, offense prec 100%, rec 90% — unchanged.
  #3 APPLIED — relationship_speed default raised from 1.0→2.0 in state.py; player.yaml updated.
     Clean turns now give +2 closeness. Threshold reachable in ~16 turns vs ~31.

Later:
  - Judge misses honorific errors (4/4 Day 7 misses). Fix: honorific rule check + subject/verb fields. Deferred.
