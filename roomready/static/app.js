/* RoomReady frontend. Every screen reads the API; the rule table is a copy of tests/rules.csv that a
   test compares with the file. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); };
  var fmt = function (s) { return esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); };
  var P = "/properties/harbour-view";
  var STAFF = [];
  var LAST_ASSIGNMENT = "";          /* the id the last Assign answer on this page carried (for Start/Finish and Send) */

  /* ---- the wire: every call goes through here; the last raw answer is shown at the bottom ---- */
  function showWire(status, headers, body) {
    var h = ["location"].filter(function (k) { return headers[k]; }).map(function (k) { return k + ": " + headers[k]; }).join("\n");
    $("wire").textContent = "HTTP " + status + (h ? "\n" + h : "") + "\n" + JSON.stringify(body, null, 2);
  }
  async function call(method, path, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) { opts.headers["content-type"] = "application/json"; opts.body = JSON.stringify(body); }
    var r = await fetch(path, opts);
    var data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    var headers = { location: r.headers.get("location") };
    showWire(r.status, headers, data);
    return { status: r.status, ok: r.ok, body: data, headers: headers };
  }
  function refusal(p) {
    if (!p) return "<b>No answer</b>";
    var extra = [];
    if (p.state) extra.push("the room is " + p.state + (p.needs ? " — it needs " + p.needs + " first" : ""));
    if (p.assigned_to) extra.push("assigned to " + p.assigned_to);
    if (p.errors) extra.push(p.errors.map(function (e) { return e.field + ": " + e.message; }).join("; "));
    return "<b>" + esc(p.title || "Not on this day yet") + "</b><br>" + esc(p.detail || "") + (extra.length ? "<br>" + esc(extra.join(" · ")) : "") +
      "<br><small class='muted'>" + (p.status || "") + " · " + esc(p.type || "") + "</small>";
  }
  function answer(okId, noId, r, okHtml) {
    $(okId).hidden = !r.ok; $(noId).hidden = r.ok;
    if (r.ok) $(okId).innerHTML = okHtml(r.body); else $(noId).innerHTML = refusal(r.body);
  }
  function nowIso() { return new Date().toISOString().replace(/\.\d{3}Z$/, "Z"); }
  function hhmm(iso) { return iso ? iso.slice(11, 16) : ""; }

  function show(screen) {
    document.querySelectorAll(".screen").forEach(function (s) { s.classList.toggle("on", s.id === screen); });
    document.querySelectorAll("#nav button").forEach(function (b) { b.classList.toggle("on", b.dataset.screen === screen); });
    var load = { board: loadBoard, work: loadWork, room: function () { loadRoom($("roomform").no.value.trim(), $("roomform").stay.value.trim()); }, rules: loadRules, api: loadApi, runtime: loadRuntime };
    if (load[screen]) load[screen]();
  }
  $("nav").addEventListener("click", function (e) { var b = e.target.closest("button[data-screen]"); if (b) show(b.dataset.screen); });

  async function staff() {
    var r = await fetch(P + "/housekeepers"); var body = await r.json();
    STAFF = body.housekeepers || [];
    return STAFF;
  }
  function nameOf(id) { var h = STAFF.filter(function (x) { return x.id === id; })[0]; return h ? h.name + " (" + id + ")" : id; }
  function options(list, selected) { return list.map(function (h) { return "<option value='" + h.id + "'" + (h.id === selected ? " selected" : "") + ">" + h.id + " " + esc(h.name) + "</option>"; }).join(""); }

  /* ---- the floor ---- */
  async function loadBoard() {
    var q = [];
    if ($("ffloor").value) q.push("floor=" + $("ffloor").value);
    if ($("fstate").value) q.push("state=" + $("fstate").value);
    if ($("ftype").value) q.push("type=" + $("ftype").value);
    var r = await call("GET", P + "/rooms" + (q.length ? "?" + q.join("&") : ""));
    if (!r.ok) { $("grid").innerHTML = "<p class='muted'>" + refusal(r.body) + "</p>"; return; }
    $("boardcount").textContent = r.body.rooms.length + " shown · " + r.body.ready + " ready · " + r.body.dirty + " dirty";
    var floors = {};
    r.body.rooms.forEach(function (x) { (floors[x.floor] = floors[x.floor] || []).push(x); });
    $("grid").innerHTML = Object.keys(floors).sort().reverse().map(function (f) {
      return "<div class='floor'><div class='floorlbl'>Floor " + f + "</div><div class='cells'>" + floors[f].map(function (x) {
        var line = x.state === "occupied" ? "guest in" : x.state.replace(/_/g, " ") + (x.assigned_to ? " · " + x.assigned_to : "") + (x.since_minutes != null ? " · " + x.since_minutes + " min" : "");
        return "<div class='room " + x.state + "' data-no='" + x.no + "'><b>" + x.no + "</b>" + x.type + "<small><br>" + esc(line) + "</small></div>";
      }).join("") + "</div></div>";
    }).join("");
    var people = await staff();
    $("staff").innerHTML = people.map(function (h) {
      return "<li><code>" + h.id + "</code> " + esc(h.name) + " — " + (h.open_assignment ? "on <b>" + h.open_assignment + "</b>" : "<span class='muted'>no room</span>") + "</li>";
    }).join("");
  }
  ["ffloor", "fstate", "ftype"].forEach(function (id) { $(id).addEventListener("change", loadBoard); });
  $("grid").addEventListener("click", function (e) {
    var t = e.target.closest(".room"); if (!t) return;
    $("roomform").no.value = t.dataset.no; $("roomform").stay.value = "";
    show("room");
  });
  $("checkoutform").addEventListener("submit", async function (e) {
    e.preventDefault();
    var f = e.target, body = { room: f.room.value.trim(), at: f.at.value.trim() };
    if (f.arrival_at.value.trim()) body.arrival_at = f.arrival_at.value.trim();
    var r = await call("POST", "/checkouts", body);
    answer("checkoutok", "checkoutno", r, function (b) {
      return "Stay <b>" + b.stay_id + "</b> · room " + b.room + " checked out at " + b.checked_out_at + " · state <b>" + b.state + "</b><br><small class='muted'>Location: " + esc(r.headers.location) + "</small>";
    });
    if (r.ok) loadBoard();
  });
  $("checkoutform").at.value = nowIso();

  /* ---- work ---- */
  async function loadWork() {
    var people = await staff();
    $("assignhk").innerHTML = options(people, $("assignhk").value || "HK03");
    $("inspecthk").innerHTML = options(people, $("inspecthk").value || "HK01");
    loadRefusals();
  }
  async function roomNow(no) {
    var r = await fetch(P + "/rooms/" + encodeURIComponent(no));
    return r.ok ? (await r.json()).state : "unknown";
  }
  $("assignform").addEventListener("submit", async function (e) {
    e.preventDefault();
    var f = e.target, no = f.room.value.trim();
    var r = await call("POST", "/assignments", { room: no, housekeeper: f.housekeeper.value });
    if (r.ok) { LAST_ASSIGNMENT = r.body.assignment_id; $("stepform").room.value = no; $("stepform").assignment.value = r.body.assignment_id; }
    answer("assignok", "assignno", r, function (b) { return "<b>" + b.assignment_id + "</b> · " + b.room + " assigned to <b>" + esc(b.assigned_to) + "</b> at " + b.assigned_at; });
  });
  async function step(verb) {
    var f = $("stepform"), no = f.room.value.trim();
    var r = await call("POST", "/assignments/" + encodeURIComponent(f.assignment.value.trim()) + "/" + verb);
    var state = r.ok ? await roomNow(no) : "";        /* the finish answer carries no state: read the room */
    answer("stepok", "stepno", r, function (b) {
      return (verb === "start" ? "Started at " + b.started_at + " — the clock is running." : "Finished at " + b.finished_at + " — <b>" + b.clean_minutes + " min</b>, stored on the assignment.") +
        " Room " + esc(no) + " is now <b>" + state + "</b>.";
    });
  }
  $("startbtn").addEventListener("click", function () { step("start"); });
  $("finishbtn").addEventListener("click", function () { step("finish"); });
  $("inspectform").addEventListener("submit", async function (e) {
    e.preventDefault();
    var f = e.target;
    var r = await call("POST", "/inspections", { room: f.room.value.trim(), inspector: f.inspector.value, result: f.result.value });
    answer("inspectok", "inspectno", r, function (b) {
      var s = b.inspection_id + ": " + b.room + " cleaned by " + esc(b.cleaned_by) + ", " + b.result + "ed by " + esc(b.inspected_by) + " — the room is <b>" + b.state + "</b>.";
      if (b.result === "pass" && b.ready_at) s += " Ready at " + b.ready_at + (b.arrival_at ? " · guest due " + b.arrival_at + " · <b>" + b.margin_minutes + " min margin</b>" : " · no arrival known, margin null") + ".";
      return s;
    });
  });
  async function loadRefusals() {
    var spec = await (await fetch("/openapi.json")).json();
    var seen = {}, rows = [];
    Object.keys(spec.paths).forEach(function (path) {
      Object.keys(spec.paths[path]).forEach(function (m) {
        var responses = spec.paths[path][m].responses || {};
        Object.keys(responses).forEach(function (status) {
          var content = responses[status].content && responses[status].content["application/problem+json"];
          if (!content || status === "500") return;
          var examples = content.examples ? Object.keys(content.examples).map(function (k) { return content.examples[k].value; }) : content.example ? [content.example] : [];
          examples.forEach(function (ex) {
            var key = ex.type + "@" + m.toUpperCase() + " " + path;
            if (seen[key]) return; seen[key] = true;
            rows.push([Number(status), ex.type, m.toUpperCase() + " " + path, Object.keys(ex).filter(function (k) { return ["type", "title", "status", "detail"].indexOf(k) < 0; }).join(", ")]);
          });
        });
      });
    });
    rows.sort(function (a, b) { return a[0] - b[0] || a[1].localeCompare(b[1]); });
    $("refusals").innerHTML = "<tr><th>Status</th><th>Type</th><th>Where</th><th>Extra fields</th></tr>" + rows.map(function (r) { return "<tr><td>" + r[0] + "</td><td><code>" + esc(r[1]) + "</code></td><td><code>" + esc(r[2]) + "</code></td><td>" + esc(r[3]) + "</td></tr>"; }).join("");
  }

  /* ---- the room card ---- */
  function eventLine(ev) {
    if (ev.kind === "checked_out") return "Checked out";
    if (ev.kind === "assigned") return "Assigned to " + esc(nameOf(ev.housekeeper));
    if (ev.kind === "started") return "Clean started";
    if (ev.kind === "finished") return "Clean finished — " + ev.clean_minutes + " min";
    if (ev.kind === "inspected") return "Inspected by " + esc(nameOf(ev.inspector)) + ": <b>" + ev.result + "</b>" + (ev.result === "fail" ? " — back to dirty" : "");
    if (ev.kind === "ready") return "Ready at the finish — no inspection needed for this type";
    return esc(ev.kind);
  }
  function readyLine(events) {
    var ready = events.filter(function (ev) { return ev.kind === "ready" || (ev.kind === "inspected" && ev.result === "pass"); }).pop();
    if (!ready) return "";
    return "ready " + hhmm(ready.at) + (ready.arrival_at ? " · guest " + hhmm(ready.arrival_at) + " · <b>" + ready.margin_minutes + " min margin</b>" : " · no arrival known");
  }
  async function loadRoom(no, stay) {
    if (!no) return;
    if (!STAFF.length) await staff();
    var r = await call("GET", P + "/rooms/" + encodeURIComponent(no));
    $("roomcard").hidden = false;
    if (!r.ok) { $("roomcard").innerHTML = refusal(r.body); return; }
    var x = r.body;
    var h = await call("GET", P + "/rooms/" + encodeURIComponent(no) + "/history" + (stay ? "?stay=" + encodeURIComponent(stay) : ""));
    var events = (h.ok && h.body && h.body.events) || [];
    var out = events.filter(function (ev) { return ev.kind === "checked_out"; })[0];
    var clean = events.filter(function (ev) { return ev.kind === "finished"; }).pop();
    var facts = [];
    if (out) facts.push("checked out " + hhmm(out.at));
    if (clean) facts.push("cleaned in <b>" + clean.clean_minutes + " min</b>");
    if (readyLine(events)) facts.push(readyLine(events));
    $("roomcard").innerHTML = "<b>" + x.no + "</b> · floor " + x.floor + " · " + x.type + " · <b>" + x.state.replace(/_/g, " ") + "</b>" + (x.assigned_to ? " · " + esc(x.assigned_to) : "") + (x.since_minutes != null ? " · for " + x.since_minutes + " min" : "") +
      (facts.length ? "<p class='facts'>" + facts.join(" · ") + " <span class='muted'>(UTC)</span></p>" : "") +
      "<p class='muted'>" + (stay ? "Stay " + esc(stay) : "The current stay") + " — every transition, in order. The database refuses to change or delete a line.</p>" +
      (events.length ? "<ul class='timeline'>" + events.map(function (ev) { return "<li><time>" + ev.at + "</time>" + eventLine(ev) + "</li>"; }).join("") + "</ul>" : "<p class='muted'>" + (h.ok ? "No events yet — the guest is still in." : "—") + "</p>");
  }
  $("roomform").addEventListener("submit", function (e) { e.preventDefault(); loadRoom(e.target.no.value.trim(), e.target.stay.value.trim()); });

  /* ---- rule book: the rows of tests/rules.csv — [status, type] under each INSPECTION_REQUIRED_FOR setting ---- */
  var RULES = [
    {"case": "checkout_ok", "tag": "checkout", "given": "214 is occupied; check it out", "all": ["201", ""], "deluxe_suite": ["201", ""], "standard_deluxe": ["201", ""]},
    {"case": "not_occupied", "tag": "checkout", "given": "214 is already dirty; check it out again", "all": ["400", "/errors/room-not-occupied"], "deluxe_suite": ["400", "/errors/room-not-occupied"], "standard_deluxe": ["400", "/errors/room-not-occupied"]},
    {"case": "malformed", "tag": "checkout", "given": "a checkout without a time", "all": ["422", "/errors/validation"], "deluxe_suite": ["422", "/errors/validation"], "standard_deluxe": ["422", "/errors/validation"]},
    {"case": "assign_dirty", "tag": "assign", "given": "214 is dirty; assign it to Sunita", "all": ["201", ""], "deluxe_suite": ["201", ""], "standard_deluxe": ["201", ""]},
    {"case": "assign_occupied", "tag": "assign", "given": "214 still has its guest; assign it", "all": ["409", "/errors/step-skipped"], "deluxe_suite": ["409", "/errors/step-skipped"], "standard_deluxe": ["409", "/errors/step-skipped"]},
    {"case": "assign_twice", "tag": "assign", "given": "Sunita is on 214; assign 214 to Devi", "all": ["409", "/errors/already-assigned"], "deluxe_suite": ["409", "/errors/already-assigned"], "standard_deluxe": ["409", "/errors/already-assigned"]},
    {"case": "start_before_assign", "tag": "sequence", "given": "214's clean failed inspection (assignment closed); start it again", "all": ["409", "/errors/step-skipped"], "deluxe_suite": ["409", "/errors/step-skipped"], "standard_deluxe": ["409", "/errors/step-skipped"]},
    {"case": "finish_before_start", "tag": "sequence", "given": "214 assigned, not started; finish", "all": ["409", "/errors/step-skipped"], "deluxe_suite": ["409", "/errors/step-skipped"], "standard_deluxe": ["409", "/errors/step-skipped"]},
    {"case": "inspect_before_finish", "tag": "sequence", "given": "214 being cleaned; inspect", "all": ["409", "/errors/step-skipped"], "deluxe_suite": ["409", "/errors/step-skipped"], "standard_deluxe": ["409", "/errors/step-skipped"]},
    {"case": "self_inspect", "tag": "inspect", "given": "Sunita finished 214; Sunita inspects", "all": ["409", "/errors/self-inspection"], "deluxe_suite": ["409", "/errors/self-inspection"], "standard_deluxe": ["409", "/errors/self-inspection"]},
    {"case": "pass", "tag": "inspect", "given": "Sunita finished 214; Grace passes it", "all": ["201", ""], "deluxe_suite": ["201", ""], "standard_deluxe": ["201", ""]},
    {"case": "fail", "tag": "inspect", "given": "Sunita finished 214; Grace fails it", "all": ["201", ""], "deluxe_suite": ["201", ""], "standard_deluxe": ["201", ""]},
    {"case": "finish_standard_no_inspection", "tag": "inspection", "given": "Sunita finishes 101 (Standard); Grace inspects", "all": ["201", ""], "deluxe_suite": ["409", "/errors/step-skipped"], "standard_deluxe": ["201", ""]},
    {"case": "finish_suite_no_inspection", "tag": "inspection", "given": "Sunita finishes 111 (Suite); Grace inspects", "all": ["201", ""], "deluxe_suite": ["201", ""], "standard_deluxe": ["409", "/errors/step-skipped"]}
  ];
  function outcome(o) { return o[0] + (o[1] ? " " + o[1].replace("/errors/", "") : ""); }
  function paintRuleTable() {
    var mode = $("ruleinspect").value;
    $("ruletable").innerHTML = "<tr><th>Case</th><th>Tag</th><th>Given, then</th><th>Expected (" + esc($("ruleinspect").options[$("ruleinspect").selectedIndex].text) + ")</th></tr>" + RULES.map(function (r) {
      var moves = !(outcome(r.all) === outcome(r.deluxe_suite) && outcome(r.all) === outcome(r.standard_deluxe));
      return "<tr" + (moves ? " class='moves'" : "") + "><td><code>" + r["case"] + "</code></td><td>" + r.tag + "</td><td>" + esc(r.given) + "</td><td><code>" + outcome(r[mode]) + "</code></td></tr>";
    }).join("");
  }
  $("ruleinspect").addEventListener("change", paintRuleTable);
  async function loadRules() {
    var r = await call("GET", "/settings");
    if (r.ok) {
      var s = r.body, types = s.inspection_required_for.join(",");
      $("settings").innerHTML = "<dt>Inspection needed for</dt><dd>" + esc(s.inspection_required_for.join(", ") || "no room type") + " — a finished clean of any other type is ready at once, margin stamped then <code>INSPECTION_REQUIRED_FOR=" + esc(types) + "</code></dd>" +
        "<dt>stall_after_minutes</dt><dd>" + s.stall_after_minutes + " <code>STALL_AFTER_MINUTES=" + s.stall_after_minutes + "</code></dd>" +
        "<dt>The sequence</dt><dd>occupied → dirty → assigned → cleaning → toinspect → ready; no step may be skipped, and the person who cleaned a room never passes it</dd>";
      $("ruleinspect").value = types === "Deluxe,Suite" ? "deluxe_suite" : types === "Standard,Deluxe" ? "standard_deluxe" : "all";
    }
    paintRuleTable();
  }

  /* ---- API ---- */
  var SAMPLES = { "POST /checkouts": { room: "214", at: nowIso() }, "POST /assignments": { room: "214", housekeeper: "HK03" }, "POST /inspections": { room: "214", inspector: "HK01", result: "pass" } };
  function samplePath(path) { return path.replace("{property}", "harbour-view").replace("{no}", "214").replace("{assignment_id}", LAST_ASSIGNMENT || "AS001"); }
  async function loadApi() {
    var r = await call("GET", "/openapi.json");
    if (!r.ok) return;
    var rows = [];
    Object.keys(r.body.paths).forEach(function (path) {
      Object.keys(r.body.paths[path]).forEach(function (m) {
        var op = r.body.paths[path][m];
        rows.push("<tr><td><code>" + m.toUpperCase() + " " + esc(path) + "</code></td><td>" + esc(op.summary || "") + "</td><td>" + Object.keys(op.responses).join(" · ") +
          "</td><td><button type='button' class='send' data-m='" + m.toUpperCase() + "' data-p='" + esc(path) + "'>Send</button></td></tr>");
      });
    });
    $("endpoints").innerHTML = "<tr><th>Call</th><th>What it does</th><th>Answers</th><th></th></tr>" + rows.join("");
  }
  $("endpoints").addEventListener("click", function (e) {
    var b = e.target.closest("button.send"); if (!b) return;
    call(b.dataset.m, samplePath(b.dataset.p), SAMPLES[b.dataset.m + " " + b.dataset.p]);
  });

  /* ---- runtime ---- */
  async function loadRuntime() {
    var r = await call("GET", "/healthz");
    $("healthdot").className = "dot " + (r.ok ? "up" : r.status === 404 ? "" : "down");
    $("healthtext").textContent = r.ok ? "up — GET /healthz " + JSON.stringify(r.body) : r.status === 404 ? "—" : "down";
    var s = await call("GET", "/settings");
    $("runtimeline").textContent = "image roomready (python:3.12-slim)" + (s.ok ? " · inspection needed for " + (s.body.inspection_required_for.join(", ") || "no type") + " (GET /settings)" : "");
  }
  var SNAPSHOT = "roomready.before-restart";
  async function boardStates() {
    var r = await call("GET", P + "/rooms");
    var states = {};
    if (r.ok) r.body.rooms.forEach(function (x) { states[x.no] = x.state; });
    return r.ok ? states : null;
  }
  $("beforebtn").addEventListener("click", async function () {
    var states = await boardStates();
    if (!states) { $("restartout").textContent = "The board did not answer."; return; }
    try { localStorage.setItem(SNAPSHOT, JSON.stringify({ at: nowIso(), rooms: states })); }
    catch (e) { $("restartout").textContent = "This browser would not keep the snapshot."; return; }
    $("restartout").textContent = "Kept " + Object.keys(states).length + " rooms' states at " + nowIso() + ". Restart the container, then press After restart.";
  });
  $("afterbtn").addEventListener("click", async function () {
    var before = null;
    try { before = JSON.parse(localStorage.getItem(SNAPSHOT) || "null"); } catch (e) { before = null; }
    if (!before) { $("restartout").textContent = "Press Before restart first."; return; }
    var now = await boardStates();
    if (!now) { $("restartout").textContent = "The board did not answer — is the container up?"; return; }
    var nos = Object.keys(before.rooms).concat(Object.keys(now).filter(function (no) { return !(no in before.rooms); }));
    var diffs = nos.filter(function (no) { return before.rooms[no] !== now[no]; }).map(function (no) { return no + ": " + (before.rooms[no] || "absent") + " → " + (now[no] || "absent"); });
    $("restartout").innerHTML = diffs.length ? "<b>Changed</b> since " + esc(before.at) + ":<br>" + diffs.map(esc).join("<br>") : "<b>Unchanged</b> — all " + nos.length + " rooms in the state they were in at " + esc(before.at) + ".";
  });

  /* ---- walkthrough: the tickets, one at a time, on top of the screens they built ---- */
  var WALK = null, stepNo = 0;
  var TAGS = { board: ["B-01", "B-02"], work: ["B-03", "B-04"], room: ["B-05", "B-06"], rules: ["B-08"], api: ["B-07"], runtime: ["B-09", "B-10"] };
  var SCREEN_NAMES = { board: "The floor", work: "Work", room: "Room", rules: "Rule book", api: "API", runtime: "Runtime" };
  function list(items) { return "<ul>" + items.map(function (s) { return "<li>" + fmt(s) + "</li>"; }).join("") + "</ul>"; }
  function acTable(rows) {
    return "<table class='tbl ac'><tr><th></th><th>given</th><th>when</th><th>then</th></tr>" + rows.map(function (r, i) {
      return "<tr><td>" + (i + 1) + "</td><td>" + fmt(r[0]) + "</td><td>" + fmt(r[1]) + "</td><td>" + fmt(r[2]) + "</td></tr>";
    }).join("") + "</table>";
  }
  function endpoint(e) {
    var h = "<div class='ep'><div class='sig'><b>" + e.m + "</b> " + esc(e.p) + "</div>";
    if (e.q) h += "<div class='muted'>? " + fmt(e.q) + "</div>";
    if (e.req) h += "<div class='muted'>request</div><pre>" + esc(JSON.stringify(e.req, null, 2)) + "</pre>";
    if (e.res) h += "<div class='muted'>response</div><pre>" + esc(JSON.stringify(e.res, null, 2)) + "</pre>";
    if (e.codes.length) h += "<table class='tbl ac'><tr><th>status</th><th>type</th><th>when</th></tr>" + e.codes.map(function (c) {
      return "<tr><td class='st " + (/^2/.test(c[0]) ? "ok" : "no") + "'>" + esc(c[0]) + "</td><td><code>" + esc(c[1]) + "</code></td><td>" + fmt(c[2]) + "</td></tr>";
    }).join("") + "</table>";
    return h + "</div>";
  }
  function paintStep() {
    var s = WALK.steps[stepNo];
    $("walkpos").textContent = "Ticket " + (stepNo + 1) + " of " + WALK.steps.length + " · " + WALK.level;
    $("walkprev").disabled = stepNo === 0; $("walknext").disabled = stepNo === WALK.steps.length - 1;
    $("walkid").textContent = s.id; $("walktitle").textContent = s.title; $("walkscene").innerHTML = fmt(s.scene);
    $("walkus").innerHTML = "As a <b>" + esc(s.story.as) + "</b>, I want to " + fmt(s.story.want) + ", so that " + fmt(s.story.so) + ".";
    $("walktry").innerHTML = "<div class='lbl'>Try it — " + SCREEN_NAMES[s.try.screen] + " screen</div><p>" + fmt(s.try.do) + "</p>" +
      "<div class='lbl'>What will happen</div><p>" + fmt(s.try.see) + "</p><button type='button' id='walkgo'>Go to " + SCREEN_NAMES[s.try.screen] + "</button>";
    $("walkgo").addEventListener("click", function () { show(s.try.screen); document.getElementById(s.try.screen).scrollIntoView({ behavior: "smooth", block: "start" }); });
    $("walkbuild").innerHTML = fmt(s.build); $("walkfollows").innerHTML = fmt(s.follows);
    $("walkcontract").innerHTML = "<p>" + fmt(s.summary) + "</p>" +
      (s.endpoints.length ? s.endpoints.map(endpoint).join("") : "<p class='muted'>No HTTP surface changes on this day — the work is in the code, the database or the container.</p>") +
      "<div class='muted' style='margin-top:8px'>What is stored</div>" + list(s.data) + "<div class='muted' style='margin-top:8px'>Rules the backend enforces</div>" + list(s.rules);
    $("walkacuser").innerHTML = acTable(s.ac_user); $("walkacapi").innerHTML = acTable(s.ac_api); $("walkdone").innerHTML = list(s.done);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function openWalk(id) {
    if (!WALK) WALK = await (await fetch("/static/walkthrough.json")).json();
    if (id) stepNo = Math.max(0, WALK.steps.findIndex(function (s) { return s.id === id; }));
    $("walk").hidden = false; $("walkbtn").classList.add("on"); paintStep();
  }
  $("walkbtn").addEventListener("click", function () { if ($("walk").hidden) openWalk(); else { $("walk").hidden = true; $("walkbtn").classList.remove("on"); } });
  $("walkclose").addEventListener("click", function () { $("walk").hidden = true; $("walkbtn").classList.remove("on"); });
  $("walkprev").addEventListener("click", function () { if (stepNo > 0) { stepNo--; paintStep(); } });
  $("walknext").addEventListener("click", function () { if (stepNo < WALK.steps.length - 1) { stepNo++; paintStep(); } });
  Object.keys(TAGS).forEach(function (screen) {
    var h2 = document.querySelector("#" + screen + " h2");
    TAGS[screen].forEach(function (id) { h2.insertAdjacentHTML("beforeend", "<span class='tag' data-step='" + id + "' title='Open this ticket in the walkthrough'>" + id + "</span>"); });
  });
  document.addEventListener("click", function (e) { var t = e.target.closest(".tag"); if (t) openWalk(t.dataset.step); });

  show("board");
})();
