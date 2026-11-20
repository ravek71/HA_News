import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

// Wersja 2 — rozszerzenia względem oryginalnej cookies-iframe-card:
// - odnawianie sesji ingress co 5 min (zamiast 10),
// - detekcja błędów w iframe (tutaj: ta sama domena => można czytać contentDocument):
//   * 401/403/brak treści  -> automatyczne odnowienie sesji i ponowne ładowanie,
//   * błąd sieci (iframe error) lub timeout 20 s -> nakładka z przyciskiem
//     „Spróbuj ponownie" + czytelny komunikat (diagnoza: 401 czy sieć/VPN).

const SESSION_REFRESH_MS = 5 * 60 * 1000;
const LOAD_TIMEOUT_MS = 20 * 1000;

const setSession = async (hass) => {
  const session = (
    await hass.callWS({
      type: "supervisor/api",
      endpoint: "/ingress/session",
      method: "post",
    })
  ).session;
  document.cookie = `ingress_session=${session};path=/api/hassio_ingress/;SameSite=Strict${
    "https:" === location.protocol ? ";Secure" : ""
  }`;
  return session;
};

class CookiesIframeV2Card extends LitElement {

  constructor() {
    super();
    this.initialized = 0;
    this.connected = 0;
    this.status = "";       // "" | "loading" | "error"
    this.statusDetail = "";
    this._loadTimer = null;
    this._loadWatched = 0;
    this._autoRetried = 0;
  }

  static getConfigElement() {
    return document.createElement("cookies-iframe-v2-editor");
  }

  static getStubConfig() {
    return {
      title: "",
      url: "https://www.home-assistant.io",
      aspect_ratio: "50%",
    };
  }

  static get properties() {
    return {
      _config: {},
      hass: { type: Object },
    };
  }

  async _setSession() {
    await setSession(this.hass);
    this.initialized = 1;
    this.requestUpdate();
  }

  connectedCallback() {
    if (this.connected === 1) {
      return;
    }
    this.connected = 1;
    if (this.initialized === 0) {
      this._setSession();
      window.setInterval(async () => {
        try {
          await setSession(this.hass);
        } catch (e) {
          console.warn("cookies-iframe-v2: odnowienie sesji nie powiodlo sie", e);
        }
      }, SESSION_REFRESH_MS);
    }
    super.connectedCallback();
  }

  updated() {
    // iframe jest w DOM dopiero po inicjalizacji — wtedy startuje pilnowanie ładowania
    if (this.initialized === 1 && this._loadWatched === 0) {
      this._loadWatched = 1;
      this._startLoadWatch();
    }
  }

  _startLoadWatch() {
    clearTimeout(this._loadTimer);
    this.status = "loading";
    this.statusDetail = "";
    this.requestUpdate();
    this._loadTimer = setTimeout(() => {
      if (this.status === "loading") {
        this.status = "error";
        this.statusDetail =
          "Timeout ładowania (20 s) — brak odpowiedzi serwera. " +
          "Sprawdź połączenie (VPN?) i spróbuj ponownie.";
        this.requestUpdate();
      }
    }, LOAD_TIMEOUT_MS);
  }

  _onIframeError() {
    clearTimeout(this._loadTimer);
    this.status = "error";
    this.statusDetail =
      "Przeglądarka nie mogła załadować strony: błąd sieci/DNS/TLS " +
      "albo odpowiedź zablokowana przez filtr (VPN z adblockingiem?).";
    this.requestUpdate();
  }

  _onIframeLoad() {
    clearTimeout(this._loadTimer);
    let doc = null;
    let frame = null;
    try {
      frame = this.shadowRoot.querySelector("iframe");
      doc = frame && frame.contentDocument;
    } catch (e) {
      doc = null; // cross-origin — nie da się sprawdzić, nie przeszkadzamy
    }
    if (!doc || !doc.body) {
      return;
    }
    const text = (doc.body.innerText || "").trim();
    const hasContent = !!doc.querySelector("a, ul, table");
    const looksLikeError =
      !hasContent &&
      (text.length < 400) &&
      (/401|403|unauthoriz|invalid|forbidden|error|brak/i.test(text) || text.length < 50);
    if (looksLikeError) {
      if (this._autoRetried === 0) {
        this._autoRetried = 1;
        this.status = "loading";
        this.statusDetail =
          "Wygląda na błąd sesji ingress (401/403) — odnawiam sesję i ładuję ponownie…";
        this.requestUpdate();
        this._doRetry();
      } else {
        this.status = "error";
        this.statusDetail =
          "Serwer zwrócił błąd. Treść odpowiedzi: " + text.slice(0, 200);
        this.requestUpdate();
      }
    } else {
      this._autoRetried = 0;
      this.status = "";
      this.requestUpdate();
    }
  }

  _reload() {
    const f = this.shadowRoot.querySelector("iframe");
    if (!f) {
      return;
    }
    let u = this._config.url;
    u += (u.indexOf("?") === -1 ? "?" : "&") + "_t=" + Date.now();
    f.src = u;
    this._startLoadWatch();
  }

  async _doRetry() {
    try {
      await setSession(this.hass);
    } catch (e) {
      this.status = "error";
      this.statusDetail = "Nie udało się odnowić sesji ingress: " + e;
      this.requestUpdate();
      return;
    }
    this._reload();
  }

  _onRetryClick() {
    this._autoRetried = 0;
    this._doRetry();
  }

  render() {
    if (this.initialized === 0) {
      return html``;
    }

    const padding = this._config.aspect_ratio ? this._config.aspect_ratio : "50%";

    return html`
      <ha-card .header=${this._config.title}>
        <div id="root" style="padding-top: ${padding}">
          <iframe
            src=${this._config.url}
            sandbox="allow-forms allow-modals allow-popups allow-pointer-lock allow-same-origin allow-scripts"
            allowfullscreen="true"
            @load=${this._onIframeLoad}
            @error=${this._onIframeError}
          ></iframe>
          ${this.status === "loading"
            ? html`<div id="overlay">${this.statusDetail || "Ładowanie…"}</div>`
            : html`<div id="overlay" class="err">
                <div>${this.statusDetail}</div>
                <button @click=${this._onRetryClick}>Spróbuj ponownie</button>
              </div>`}
        </div>
      </ha-card>
    `;
  }

  setConfig(config) {
    if (!config.url) {
      throw new Error("URL required");
    }
    this._config = config;
  }

  static get styles() {
    return css`
      ha-card {
        overflow: hidden;
      }
      #root {
        width: 100%;
        position: relative;
      }
      iframe {
        position: absolute;
        border: none;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
      }
      #overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: .6rem;
        padding: 1rem;
        text-align: center;
        font-size: .85rem;
        background: rgba(127, 127, 127, .18);
        z-index: 1;
      }
      #overlay.err {
        color: #ef6c00;
      }
      #overlay button {
        padding: .35rem 1rem;
        border: 1px solid #8884;
        border-radius: .5rem;
        background: transparent;
        color: inherit;
        cursor: pointer;
        font-size: .85rem;
      }
    `;
  }

}

customElements.define("cookies-iframe-v2", CookiesIframeV2Card);

const SCHEMA = [
  { name: "title", selector: { text: {} } },
  {
    name: "",
    type: "grid",
    schema: [
      { name: "url", required: true, selector: { text: {} } },
      { name: "aspect_ratio", selector: { text: {} } },
    ],
  },
];

class CookiesIframeV2CardEditor extends LitElement {

  static get properties() {
    return {
      _config: {},
      hass: { type: Object },
    };
  }

  setConfig(config) {
    this._config = config;
  }

  render() {
    return html`
      <ha-form
        @value-changed=${this._valueChanged}
        .hass=${this.hass}
        .data=${this._config}
        .schema=${SCHEMA}
      ></ha-form>
    `;
  }

  _valueChanged(ev) {
    const event = new Event("config-changed", {
      bubbles: true,
      composed: true,
    });
    event.detail.value = ev.detail.value;
    this.dispatchEvent(event);
  }
}

customElements.define("cookies-iframe-v2-editor", CookiesIframeV2CardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "cookies-iframe-v2",
  name: "Cookies Iframe Card V2 (auto-retry + diagnostics)",
  preview: false,
  description: "iframe card with supervisor ingress cookies; auto session refresh, error overlay and retry",
});
