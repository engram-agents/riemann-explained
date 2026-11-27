/* THE STATEMENT CARD's pieces (spec H, amendments 1 and 2). A pure builder: buildStatement(...) -> { lead, tail }, two arrays of nodes that app.js hands to
   the sheet (sheet.js showCard puts `lead` between the status line and the repository's note, `tail` after the note). In the card's order:

     lead  p.decl-name            the full Lean name in <code>
           div.decl-heading       only when the step has a heading: p.decl-heading-label, then the heading through renderNote (the maths face when on)
           p.note-label, p.decl-no-note    only when the step has NO note (the label, then decl_no_note); with a note the sheet draws label, source and note
     [the sheet draws the doc-string here, as it draws a file's note, with the label swapped to spine_content_label]
     tail  div.decl-lean          button.sheet-tool (aria-expanded) + div.decl-lean-body (hidden): pre.decl-lean-code > code (the statement as ONE text node),
                                  and, only when `variables` is true, p.decl-lean-note
           div.decl-uses.decl-uses-here, div.decl-uses.decl-uses-elsewhere    a heading line with {n} (text) and, only when the list is not empty, a ul:
                                  here: li > a[href '#id'] (the title as the page knows it, else the bare id); elsewhere: li > code(name), in an a[href '#step'] with a step
           div.decl-prompt      [p.decl-reading-none, only when the optional string decl_reading_none is present,] button.sheet-tool (copy), p[role=status] (empty until a copy succeeds), pre.decl-prompt-text (hidden; shown with its text
                                  SELECTED when the clipboard is missing or refuses), and, always last, p.decl-prompt-note

   Everything the data gives (name, text, prompt, heading, titles) enters as a text node through el() and renderNote; nothing is parsed, nothing is filled into
   the prompt, and every listener carries the page's abort signal. The two buttons live inside the card body, never in the sheet's tools row (amendment 2). */
import { hashFor, titleChildren } from "./dom.js";
import { renderNote } from "./note.js";

const fill = (template, n) => String(template).replace("{n}", () => String(n));

/* The maths-face words of a STATEMENT card's doc-string: the same four words, but the label is spine_content_label in the maths view as in the exact one
   (design note section 4 item 2); note_label_typeset is never used on a statement card. null stays null (the maths face is off). */
export function docstringTypeset(strings, typesetWords) {
  return typesetWords ? { ...typesetWords, label: strings.spine_content_label } : null;
}

/* params: strings, decl (data.js step.decl), hasNote (the step has a note: the sheet draws the doc-string), titleOf(id) -> a title or undefined,
   el (dom.js), doc, signal, typeset (the maths face is on). */
export function buildStatement({ strings, decl, hasNote, titleOf, el, doc, signal, typeset }) {
  const win = doc.defaultView;
  const text = (s) => doc.createTextNode(String(s));
  const lead = [el("p", { class: "decl-name" }, [el("code", {}, [decl.name])])];
  if (typeof decl.heading === "string") {
    const body = el("div", { class: "decl-heading-body" }, []);
    body.appendChild(renderNote(decl.heading, el, !!typeset));
    lead.push(el("div", { class: "decl-heading" }, [el("p", { class: "decl-heading-label" }, [strings.decl_heading_label]), body]));
  }
  if (!hasNote) lead.push(el("p", { class: "note-label" }, [strings.spine_content_label]), el("p", { class: "decl-no-note" }, [strings.decl_no_note]));

  // 4. the Lean statement behind a button
  const leanBtn = el("button", { type: "button", class: "sheet-tool", "aria-expanded": "false" }, [strings.decl_show_lean]);
  const leanKids = [el("pre", { class: "decl-lean-code" }, [el("code", {}, [decl.text])])];
  if (decl.variables) leanKids.push(el("p", { class: "decl-lean-note" }, [strings.decl_lean_note]));
  const leanBody = el("div", { class: "decl-lean-body" }, leanKids);
  leanBody.hidden = true;
  leanBtn.addEventListener("click", () => {
    const show = leanBody.hidden;
    leanBody.hidden = !show;
    leanBtn.setAttribute("aria-expanded", show ? "true" : "false");
    leanBtn.replaceChildren(text(show ? strings.decl_hide_lean : strings.decl_show_lean));
  }, { signal });
  const lean = el("div", { class: "decl-lean" }, [leanBtn, leanBody]);

  // 5. uses: a heading line with the count, and a list only when there is something to list
  const usesHere = el("div", { class: "decl-uses decl-uses-here" }, [el("p", { class: "decl-uses-line" }, [fill(strings.decl_uses_here, decl.usesHere.length)])]);
  if (decl.usesHere.length > 0) {
    usesHere.appendChild(el("ul", {}, decl.usesHere.map((id) => {
      const t = titleOf(id);
      return el("li", {}, [el("a", { href: hashFor(id) }, typeof t === "string" && t !== "" ? titleChildren(t, el) : [id])]);
    })));
  }
  const usesElse = el("div", { class: "decl-uses decl-uses-elsewhere" }, [el("p", { class: "decl-uses-line" }, [fill(strings.decl_uses_elsewhere, decl.usesElsewhere.length)])]);
  if (decl.usesElsewhere.length > 0) {
    usesElse.appendChild(el("ul", {}, decl.usesElsewhere.map((u) => {
      const name = el("code", {}, [u.name]);
      return el("li", {}, [typeof u.step === "string" ? el("a", { href: hashFor(u.step) }, [name]) : name]);
    })));
  }

  // 6. the prompt for the reader's own assistant: copy, or show it selected when the clipboard cannot
  const copyBtn = el("button", { type: "button", class: "sheet-tool" }, [strings.decl_prompt_button]);
  const status = el("p", { class: "decl-prompt-status", role: "status" }, []);
  const fallback = el("pre", { class: "decl-prompt-text" }, [decl.prompt]);
  fallback.hidden = true;
  const copied = text(strings.decl_prompt_copied);
  let copiedShown = false;
  copyBtn.addEventListener("click", async () => {
    let ok = false;
    try { await win.navigator.clipboard.writeText(decl.prompt); ok = true; } catch (e) { ok = false; }
    if (ok) {
      if (!copiedShown) { status.appendChild(copied); copiedShown = true; }
      return;
    }
    if (copiedShown) { status.removeChild(copied); copiedShown = false; }
    fallback.hidden = false;
    try { win.getSelection().selectAllChildren(fallback); } catch (e) { /* the reader selects by hand */ }
  }, { signal });
  const reading = typeof strings.decl_reading_none === "string" && strings.decl_reading_none !== "" ? [el("p", { class: "decl-reading-none" }, [strings.decl_reading_none])] : [];   // optional: ONE line directly above the button
  const prompt = el("div", { class: "decl-prompt" }, [...reading, copyBtn, status, fallback, el("p", { class: "decl-prompt-note" }, [strings.decl_prompt_note])]);

  return { lead, tail: [lean, usesHere, usesElse, prompt] };
}
