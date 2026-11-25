// Classic script, loaded first: counts the event listeners that are live (added and not removed), by wrapping
// addEventListener / removeEventListener, and records Content-Security-Policy violations.
(function () {
  window.__csp = [];
  document.addEventListener("securitypolicyviolation", function (e) { window.__csp.push(e.violatedDirective + " " + e.blockedURI); });
  var live = [];
  function same(a, b) { return a.t === b.t && a.type === b.type && a.fn === b.fn && a.cap === b.cap; }
  function cap(o) { return typeof o === "boolean" ? o : !!(o && o.capture); }
  var add = EventTarget.prototype.addEventListener, rem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, o) {
    var e = { t: this, type: type, fn: fn, cap: cap(o) };
    if (fn && !live.some(function (x) { return same(x, e); })) live.push(e);
    return add.apply(this, arguments);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, o) {
    var e = { t: this, type: type, fn: fn, cap: cap(o) };
    live = live.filter(function (x) { return !same(x, e); });
    return rem.apply(this, arguments);
  };
  window.__ls = { live: function () { return live.length; }, types: function () { return live.map(function (x) { return x.type; }); } };
})();
