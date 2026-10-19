import { afterEach, describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../../", import.meta.url));
const read = (name) => readFileSync(resolve(root, name), "utf8");
const script = (name) => read(`docs/assets/js/${name}.js`);
const windows = [];
function dom(body = "", query = "") {
    const instance = new JSDOM(body, { url: `https://ekklesia.gr/embed/vote.html${query}`, runScripts: "outside-only" });
    windows.push(instance);
    const w = instance.window;
    w.setInterval = (() => 1);
    w.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
    w.IntersectionObserver = class {
        observe() { }
        disconnect() { }
    };
    const run = (name) => w.eval(script(name));
    return { w, document: w.document, run };
}
afterEach(() => { windows.splice(0).forEach(d => d.window.close()); });
// Verified against origin/main 4ff02f8c: Greek on each load, no storage accesses.
const languages = ["community-language", "landing-language", "govgr-dimos", "wiki-language", "wiki-faq-2", "wiki-index-2", "wiki-modules-2", "wiki-roadmap-2", "wiki-zk-voting-1", "wiki-broadcasting-2", "wiki-audit-2", "mirror-setup-language", "representative-language"];
describe("old language contracts", () => {
    it.each(languages)("%s preserves Greek default and EN → EL without storage", name => {
        const { w, document, run } = dom('<button id="langBtn">EN</button><span id="langFlag">EN</span><p data-el="Ελληνικά" data-en="English">Ελληνικά</p>');
        const get = vi.spyOn(w.Storage.prototype, "getItem").mockReturnValue("en");
        const set = vi.spyOn(w.Storage.prototype, "setItem");
        run(name);
        expect(w.currentLang).toBe("el");
        w.toggleLang();
        expect(document.querySelector("p").textContent).toBe("English");
        w.toggleLang();
        expect(document.querySelector("p").textContent).toBe("Ελληνικά");
        expect(get).not.toHaveBeenCalled();
        expect(set).not.toHaveBeenCalled();
    });
    it("landing preserves the old textContent swap even when an attribute contains markup", () => {
        const { w, document, run } = dom('<span id="langFlag"></span><p data-el="EL" data-en="&lt;strong&gt;EN&lt;/strong&gt;">EL</p>');
        run("landing-language");
        w.toggleLang();
        expect(document.querySelector("p").textContent).toBe("<strong>EN</strong>");
        expect(document.querySelector("strong")).toBeNull();
    });
});
it("all published external scripts defer in source order, including config and vendors", () => {
    function pages(dir) {
        return readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? pages(resolve(dir, e.name)) : e.name.endsWith(".html") ? [resolve(dir, e.name)] : []);
    }
    for (const path of [...pages(resolve(root, "docs")), resolve(root, "apps/representative/web/index.html")]) {
        for (const tag of readFileSync(path, "utf8").matchAll(/<script\b[^>]*\bsrc=[^>]*>/gi)) {
            expect(tag[0], path).toMatch(/\bdefer\b/);
            expect(tag[0], path).not.toMatch(/\basync\b/);
        }
    }
    for (const [page, dependencies] of [
        ["docs/tickets/index.html", ["config.js", "polis.js", "tickets-board.js"]],
        ["docs/tickets/auth/callback.html", ["config.js", "tickets-callback.js"]],
        ["docs/demo/bills.html", ["data.js", "demo-bills.js"]],
        ["docs/embed/qr-login.html", ["qrcode-vendor.js", "qr-login.js"]],
        ["docs/embed/vote.html", ["embed-ui.js", "embed-vote.js"]],
        ["docs/index.html", ["landing-folds.js", "landing-cycle.js"]],
    ]) {
        const html = read(page);
        const positions = dependencies.map(dependency => html.indexOf(dependency));
        expect(positions.every(p => p >= 0), page).toBe(true);
        expect(positions, page).toEqual([...positions].sort((a, b) => a - b));
    }
});
it.each(["community-modals", "legal-language", "wiki-index-2", "demo-admin", "demo-bills", "tickets-board", "representative-app", "qr-login", "tickets-callback"])("%s tolerates absent optional DOM nodes", async (name) => {
    const { w, run } = dom();
    w.localStorage.setItem("rep_token", "existing");
    expect(() => run(name)).not.toThrow();
    await new Promise(resolve => setImmediate(resolve));
});
it("mirror status handles a missing m1 on success and fallback; HLR has one implementation", () => {
    const { w, document } = dom('<div id="mirrorSandboxRow"></div><span id="mirrorSandboxDot"></span><span id="mirrorSandboxText"></span>');
    const finance = script("community-finance");
    w.eval("function t(el) { return el; }\n" + finance.slice(finance.indexOf("  function setMirrorStatus("), finance.indexOf("  function fetchMirrorStatus(")));
    for (const status of ["online", "degraded", "offline"])
        expect(() => w.setMirrorStatus(status, 12)).not.toThrow();
    expect(document.getElementById("mirrorSandboxText").textContent).toBe("Offline");
    expect(finance).not.toContain("function switchHlrTab");
    expect(script("community-tabs").match(/function switchHlrTab/g)).toHaveLength(1);
});
const hostile = '<img src=x onerror="alert(1)"><svg onload="alert(2)">';
const votes = { yes_count: 4, no_count: 3, abstain_count: 1, total_votes: 8, yes_percent: 50, no_percent: 37.5, abstain_percent: 12.5 };
it.each(["embed-results", "embed-vote"])("%s renders hostile API strings as text with no HTML sink", name => {
    const { w, document, run } = dom('<div id="widget"><div id="loader"></div></div>');
    run("embed-ui");
    run(name);
    const sink = vi.spyOn(w.Element.prototype, "innerHTML", "set");
    w.render({ title_el: hostile, pill_el: hostile, status: hostile, party_votes_parliament: { p: "YES" } }, { ...votes, total_votes: hostile, yes_percent: hostile });
    expect(document.querySelector(".title").textContent).toBe(hostile);
    expect(document.querySelector("#widget img, #widget svg, #widget [onerror], #widget [onload]")).toBeNull();
    expect(sink).not.toHaveBeenCalled();
    w.render({ title_en: hostile, status: "ACTIVE" }, votes);
    expect(document.querySelector(".title").textContent).toBe(hostile);
    expect(document.querySelector(name === "embed-results" ? ".bar-yes" : ".bar-yes").style.width).toBe("50%");
});
it("QR authentication accepts only the expected same-origin child window", () => {
    const { w, document, run } = dom('<div id="widget"><div id="loader"></div></div>');
    run("embed-ui");
    run("embed-vote");
    w.render({ status: "ACTIVE" }, votes);
    const child = document.getElementById("qr-frame").contentWindow;
    const data = { type: "ekklesia-qr-auth", status: "authenticated", session_id: "fixture-session" };
    for (const [origin, source] of [["https://attacker.invalid", child], [w.location.origin, w]]) {
        w.dispatchEvent(new w.MessageEvent("message", { origin, source, data }));
        expect(w.authState.authenticated).toBe(false);
        expect(document.querySelector(".vote-btn").disabled).toBe(true);
    }
    w.dispatchEvent(new w.MessageEvent("message", { origin: w.location.origin, source: child, data }));
    expect(w.authState.session_id).toBe("fixture-session");
    expect(document.querySelector(".vote-btn").disabled).toBe(false);
});
it("QR auth sends session credentials only to the explicit same-origin parent", async () => {
    const { w, run } = dom('<div id="timer"></div><div id="status-success"></div>');
    const postMessage = vi.fn();
    Object.defineProperty(w, "parent", { value: { postMessage } });
    w.fetch = vi.fn(async () => ({ json: async () => ({ status: "authenticated", nullifier_hash: "fixture" }) }));
    run("qr-login");
    w.sessionId = "fixture-session";
    await w.pollSession();
    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({ type: "ekklesia-qr-auth", session_id: "fixture-session" }), "https://ekklesia.gr");
});

it('the single HLR tab controller switches both panels and tolerates missing nodes', () => {
    const { w, document, run } = dom('<div id="hlrPanelPrimary"></div><div id="hlrPanelFallback"></div><button id="hlrTabPrimary"></button><button id="hlrTabFallback"></button>');
    run('community-tabs');
    w.switchHlrTab('fallback');
    expect(document.getElementById('hlrPanelPrimary').style.display).toBe('none');
    expect(document.getElementById('hlrPanelFallback').style.display).toBe('');
    w.switchHlrTab('primary');
    expect(document.getElementById('hlrPanelPrimary').style.display).toBe('');
    expect(document.getElementById('hlrPanelFallback').style.display).toBe('none');
    document.body.replaceChildren();
    expect(() => w.switchHlrTab('fallback')).not.toThrow();
});

it.each(['https://publisher.invalid/article', ''])('vote notifications use only the explicit embedding origin: %s', async referrer => {
    const { w, document, run } = dom('<div id="widget"><div id="loader"></div></div>');
    Object.defineProperty(document, 'referrer', { value: referrer });
    const postMessage = vi.fn();
    Object.defineProperty(w, 'parent', { value: { postMessage } });
    w.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ success: true }) }));
    run('embed-ui'); run('embed-vote'); w.render({ status: 'ACTIVE' }, votes);
    w.authState.authenticated = true; w.authState.session_id = 'fixture-session';
    await w.castVote('YES');
    if (referrer) expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({ type: 'ekklesia-vote-done' }), 'https://publisher.invalid');
    else expect(postMessage).not.toHaveBeenCalled();
});
