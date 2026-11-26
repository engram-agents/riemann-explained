/* The sheet: a bottom sheet under 768 px, a side panel above (that is CSS). It shows ONE thing at a time: a card's
   own <article> (moved in with appendChild and moved back to a placeholder comment on close, R2), the About
   content (builder markup, moved the same way) or the key (generated). The List markup is never copied or reparsed.

   CLASS TABLE this module sets or honours (all fixed here, none from data):
     graph-sheet        on the sheet element (the comment script finds it with article.closest('.graph-sheet'))
     comments-editing   set and removed ONLY by the comment script; graph.css makes the sheet full height with it
     graph-sheet-body   the body container; its SINGLE child is the moved root (a card's <article>, the About block's root,
                        or the generated key); `sheetclose` is dispatched on that root, `sheetcloserequest` from anywhere in it
                        runs close()
     claim-clamped      on the sheet body while the claim is clamped to 10 lines (graph.css)
     sheet-status, sheet-tool, crumbs, crumb, crumb-here, crumb-role   chrome this module creates
     note-label, note-source, note-body   the repository's note, only when the card has one (info.note), directly after the status line
     note-typeset-line, note-toggle   only when the page says the maths face is on (info.note.typeset): the line under the source line (told only of
                        the maths-type view) and the button that swaps the rendering for the exact text and back (aria-pressed true = exact text);
                        note-exact on the body while the exact text is shown. A card shown again always starts on the rendering.
     readings, reading, reading-body, reading-by   our reading notes, only when the card's step carries some (info.readings): one div.readings below the
                        repository's note (or where it would be), holding an h4, a p, then per reading a div.reading carrying data-id (the reading's id, checked
                        by data.js; dom.js's own attribute) with an h5, a div.reading-body (rendered by note.js, the maths face on exactly as for the repository's note) and a p.reading-by.
                        NONE of the repository's frame: no label, no source line, no typeset line, no button, no review state.

   CLOSING: every way the sheet closes goes through close(), the ONE close function. It first dispatches a cancelable
   `sheetclose` event on the thing shown; if a listener cancels it, the sheet stays open and nothing moves. A
   bubbling `sheetcloserequest` from inside the sheet runs the same close(). */
import { el, titleChildren } from "./dom.js";
import { renderNote, exactNote } from "./note.js";

export function createSheet(parts, strings, hooks, signal) {
  const { root, crumbs, tools, body, closeButton } = parts;
  const doc = root.ownerDocument;
  const win = doc.defaultView;
  let cur = null;   // { node, home, details: [{d, open}], status, noteEls, id (a card), parts, partsOpen }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function restoreDetails(rec) {
    for (const x of rec.details) x.d.open = x.open;
  }

  /* The restore half of close(): everything moved or added goes back, so the page's markup is as it was. */
  function release(rec) {
    if (rec.status && rec.status.parentNode) rec.status.parentNode.removeChild(rec.status);
    for (const x of rec.noteEls || []) if (x.parentNode) x.parentNode.removeChild(x);
    restoreDetails(rec);
    if (rec.home) {
      if (rec.home.parentNode) {
        rec.home.parentNode.insertBefore(rec.node, rec.home);
        rec.home.parentNode.removeChild(rec.home);
      }
    } else if (rec.node.parentNode) {
      rec.node.parentNode.removeChild(rec.node);
    }
    clear(crumbs);
    clear(tools);
    body.classList.remove("claim-clamped");
    if (rec.sheetClass) root.classList.remove(rec.sheetClass);
    root.hidden = true;
    cur = null;
  }

  function close() {
    if (!cur) return true;
    const ev = new win.CustomEvent("sheetclose", { cancelable: true });
    cur.node.dispatchEvent(ev);
    if (ev.defaultPrevented) return false;
    release(cur);
    return true;
  }

  /* For the fallback only: put everything home even if a listener would have cancelled. */
  function dispose() { if (cur) release(cur); }

  function adopt(node, moveHome) {
    const rec = { node, home: null, details: [], status: null };
    if (moveHome) {
      rec.home = doc.createComment("");
      node.parentNode.insertBefore(rec.home, node);
    }
    node.querySelectorAll("details").forEach((d) => { rec.details.push({ d, open: d.open }); d.open = false; });
    body.appendChild(node);
    root.hidden = false;
    cur = rec;
    return rec;
  }

  /* The last entry is the open card itself (not a link) unless the page says the list stops at the parent (currentListed false): then every
     entry is an ancestor and stays a link. */
  function crumbList(list, currentListed) {
    const items = list.map((c, i) => {
      const last = currentListed && i === list.length - 1;
      const kids = [];
      if (typeof c.role === "string" && c.role !== "") kids.push(el("span", { class: "crumb-role" }, [c.role]));
      kids.push(...titleChildren(c.title));
      return el("li", {}, [last ? el("span", { class: "crumb-here" }, kids) : el("button", { type: "button", class: "crumb", "data-id": c.id }, kids)]);
    });
    if (items.length === 0) return null;   // no ancestor, no landmark: an empty labelled nav is noise to a screen reader
    return el("nav", { "aria-label": strings.crumb_label, class: "crumbs" }, [el("ol", {}, items)]);
  }

  /* showCard / showPanel return false when the current content refused to close. */
  function showCard(article, info) {
    if (!close()) return false;
    const rec = adopt(article, true);
    rec.id = info.id;          // the id this sheet shows: an engine event about any other id never touches it
    if (info.sheetClass) { root.classList.add(info.sheetClass); rec.sheetClass = info.sheetClass; }   // a token from the page's own table
    clear(crumbs);
    const nav = crumbList(info.crumbs, info.currentListed !== false);
    if (nav) crumbs.appendChild(nav);
    const claim = article.querySelector(".claim");
    /* The status line is built only for a non-empty status: a null or empty status gets no element (the page's
       own path always passes a string today), so the release step finds rec.status null and the card's own content is first under the title. */
    if (typeof info.status === "string" && info.status !== "") {
      rec.status = el("p", { class: "sheet-status" }, [info.status]);
      if (claim && claim.parentNode) claim.parentNode.insertBefore(rec.status, claim.nextSibling);
      else article.insertBefore(rec.status, article.firstChild);
    }
    /* The repository's note, when the card has one: the label, the source line (text only, never a link), then the note rendered by note.js. They go
       directly after the status line (after the claim when there is none), and the restore half of close takes them out again. */
    if (info.note) {
      const n = info.note, t = n.typeset || null;
      const label = el("p", { class: "note-label" }, [t ? t.label : n.label]);
      const source = el("p", { class: "note-source" }, n.sourceParts);
      const noteBody = el("div", { class: "note-body" }, []);
      noteBody.appendChild(renderNote(n.text, el, !!t));
      const kids = [label, source];
      if (t) {
        /* The maths-face view: the line and the button, and one function that sets everything the two views differ in. */
        const line = el("p", { class: "note-typeset-line" }, [t.line]);
        const toggle = el("button", { type: "button", class: "note-toggle", "aria-pressed": "false" }, [t.exactButton]);
        let exact = false;
        const setView = (showExact) => {
          exact = showExact;
          clear(label); label.appendChild(doc.createTextNode(exact ? n.label : t.label));
          clear(noteBody);
          noteBody.appendChild(exact ? exactNote(n.text, el) : renderNote(n.text, el, true));
          noteBody.classList.toggle("note-exact", exact);
          clear(toggle); toggle.appendChild(doc.createTextNode(exact ? t.renderButton : t.exactButton));
          toggle.setAttribute("aria-pressed", exact ? "true" : "false");
          if (exact && line.parentNode) line.parentNode.removeChild(line);
          else if (!exact && !line.parentNode && source.parentNode) source.parentNode.insertBefore(line, source.nextSibling);
        };
        toggle.addEventListener("click", () => setView(!exact), { signal });
        kids.push(line, toggle);
      }
      kids.push(noteBody);
      rec.noteEls = kids;
      const first = article.firstChild;
      let tail = rec.status || (claim && claim.parentNode ? claim : null);
      for (const k of kids) {
        if (tail) { tail.parentNode.insertBefore(k, tail.nextSibling); tail = k; } else article.insertBefore(k, first);
      }
    }
    /* Our reading notes: one section directly after the repository's note (after the status line, or the claim, when there is none). */
    if (info.readings) {
      const section = buildReadings(info.readings);
      const noteEls = rec.noteEls || [];
      const tail = (noteEls.length > 0 ? noteEls[noteEls.length - 1] : null) || rec.status || (claim && claim.parentNode ? claim : null);
      if (tail && tail.parentNode) tail.parentNode.insertBefore(section, tail.nextSibling);
      else article.insertBefore(section, article.firstChild);
      rec.noteEls = noteEls.concat([section]);
    }
    clear(tools);
    if (info.canParts) {
      const b = el("button", { type: "button", class: "sheet-tool" }, [info.partsOpen ? strings.close_parts : strings.open_parts]);
      rec.partsOpen = !!info.partsOpen;
      b.addEventListener("click", () => (rec.partsOpen ? hooks.closeParts(info.id) : hooks.openParts(info.id)), { signal });
      rec.parts = b;
      tools.appendChild(b);
    }
    clamp(claim);
    body.scrollTop = 0;
    return true;
  }

  /* The readings section. Everything from data goes in as text (el's children) or through note.js's renderer; the reading's id is the element's `data-id`,
     set by el() like every attribute (dom.js checks its shape). */
  function buildReadings(r) {
    const section = el("div", { class: "readings" }, [el("h4", {}, [r.heading]), el("p", {}, [r.about])]);
    for (const item of r.items) {
      const box = el("div", { class: "reading", "data-id": item.id }, [el("h5", {}, [item.title])]);
      const text = el("div", { class: "reading-body" }, []);
      text.appendChild(renderNote(item.text, el, r.typeset));
      box.appendChild(text);
      box.appendChild(el("p", { class: "reading-by" }, item.byline));
      section.appendChild(box);
    }
    return section;
  }

  /* Scrolls the sheet body so that the reading's element (`.readings [data-id=id]`, found by comparing, never by a selector built from data) is at its
     top, as far as the scroll allows. False when no such element is in the sheet. */
  function scrollToReading(id) {
    if (!cur) return false;
    for (const e of body.querySelectorAll(".readings [data-id]")) {
      if (e.getAttribute("data-id") !== id) continue;
      body.scrollTop += e.getBoundingClientRect().top - body.getBoundingClientRect().top;
      return true;
    }
    return false;
  }

  function showPanel(node, homeIt) {
    if (!close()) return false;
    adopt(node, homeIt);
    clear(crumbs);
    clear(tools);
    body.scrollTop = 0;
    return true;
  }

  /* A claim taller than 10 lines shows 10 and a 'Show the whole claim' button. The clamp is a class on the body, so
     the article itself gets no class, style or attribute from us. */
  function clamp(claim) {
    if (!claim) return;
    body.classList.add("claim-clamped");
    if (claim.scrollHeight <= claim.clientHeight + 1) { body.classList.remove("claim-clamped"); return; }
    const b = el("button", { type: "button", class: "sheet-tool" }, [strings.claim_more]);
    b.addEventListener("click", () => {
      const clamped = body.classList.toggle("claim-clamped");
      clear(b);
      b.appendChild(doc.createTextNode(clamped ? strings.claim_more : strings.claim_less));
    }, { signal });
    tools.appendChild(b);
  }

  /* The parts button always reflects the open state of the SHOWN id: an event for any other id changes nothing. */
  function setPartsOpen(id, open) {
    if (!cur || !cur.parts || cur.id !== id) return;
    cur.partsOpen = !!open;
    clear(cur.parts);
    cur.parts.appendChild(doc.createTextNode(open ? strings.close_parts : strings.open_parts));
  }

  closeButton.addEventListener("click", () => hooks.closeButton(), { signal });
  root.addEventListener("sheetcloserequest", () => close(), { signal });
  crumbs.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest("button[data-id]");
    if (b) hooks.go(b.getAttribute("data-id"));
  }, { signal });
  body.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a");
    const h = a && a.getAttribute("href");
    if (h && h.charAt(0) === "#") { e.preventDefault(); hooks.go(h.slice(1)); }
  }, { signal });

  return {
    close, dispose, showCard, showPanel, setPartsOpen, scrollToReading,
    isOpen: () => cur !== null,
    shown: () => (cur ? cur.node : null),
  };
}
