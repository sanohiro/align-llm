# Validate the provider envelope separately from the reviewer's verdict.
def require($ok; $message): if $ok then . else error($message) end;
def inspection_tool: . == "view_file" or . == "grep_search";
def closed_fences:
  reduce (split("\n")[]) as $line ({char: null, width: 0};
    ($line | [capture("^ {0,3}(?<run>`{3,}|~{3,})(?<info>.*)$")] | .[0]) as $fence
    | if $fence == null then .
      elif .char == null then
        if ($fence.run | startswith("~")) or ($fence.info | contains("`") | not) then
          {char: $fence.run[0:1], width: ($fence.run | length)}
        else . end
      elif $fence.run[0:1] == .char and ($fence.run | length) >= .width
          and ($fence.info | test("^[ \\t]*$")) then
        {char: null, width: 0}
      else . end)
  | .char == null;

. as $events
| require(length >= 2 and all(.[]; type == "object"); "invalid event stream")
| require([.[] | select(.event == "init")] | length == 1; "expected one init")
| require([.[] | select(.event == "result")] | length == 1; "expected one result")
| require(.[0].event == "init" and .[-1].event == "result"; "misordered stream")
| .[0] as $start
| .[-1].result as $result
| require($start.init.model == "gemini-3.8-flash-high"
    and $start.init.agent == "align-llm-reviewer"
    and $start.init.cwd == $root; "wrong model, agent or workspace")
| require(($start.conversation_id | type) == "string"
    and ($start.conversation_id | test("^[A-Za-z0-9-]+$"))
    and $start.conversation_id == $result.conversation_id; "invalid conversation identity")
| require($result.status == "SUCCESS" and ($result.num_turns | type) == "number"
    and $result.num_turns > 0 and ($result.num_turns | floor) == $result.num_turns
    and (($result.denied_actions // []) | type) == "array"
    and (($result.denied_actions // []) | length) == 0
    and ($result.error // "") == ""; "incomplete provider result")
| require(all($events[];
    if .event == "step_update" then
      (.step_update.conversation_id == $start.conversation_id)
      and .step_update.subagent_info == null
      and (if .step_update.step_type == "tool" then
        (.step_update.tool_name | inspection_tool)
        and ((.step_update.tool_info.name // .step_update.tool_name) | inspection_tool)
      else .step_update.tool_name == null and .step_update.tool_info == null end)
    else .event == "init" or .event == "result" end); "invalid or non-inspection event")
| require(($result.response | type) == "string" and ($result.response | length) > 0;
    "empty review response")
| require($result.response | closed_fences; "verdict inside an unfinished code fence")
| ($result.response | split("\n") | map(select(test("\\S")))) as $lines
| require([$lines[] | select(startswith("ALIGN_REVIEW_VERDICT="))] | length == 1;
    "expected one verdict")
| require($lines[-1] == "ALIGN_REVIEW_VERDICT=CLEAN"
    or $lines[-1] == "ALIGN_REVIEW_VERDICT=FINDINGS"; "missing complete terminal verdict")
| {conversation: $start.conversation_id, response: $result.response,
   verdict: ($lines[-1] | split("=")[1])}
