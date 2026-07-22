"""
ui.py — Tkinter arayüzü
Sekmeler:
  1. Bağlantı     → Spreadsheet ID, credentials, sayfa adları
  2. Sütunlar     → Alıcı ve gönderici sütun isimleri
  3. Şablonlar    → 5 template (4 + hatırlatma) + konu + CC/BCC + ekler
  4. Ayarlar      → Bekleme süresi, hatırlatma günü, limit
  5. Gönderim     → Başlat/Durdur + canlı log
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import logging
import os

import config as cfg
import sheets
import engine

logger = logging.getLogger(__name__)


# ── Renk paleti ──────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
PANEL    = "#2a2a3e"
ACCENT   = "#7c6af7"
ACCENT2  = "#5ba3f5"
TEXT     = "#cdd6f4"
SUBTEXT  = "#a6adc8"
SUCCESS  = "#a6e3a1"
WARNING  = "#f9e2af"
ERROR    = "#f38ba8"
ENTRY_BG = "#313244"
BTN_BG   = "#45475a"


def _style(root: tk.Tk):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=ENTRY_BG,
                 bordercolor=PANEL, troughcolor=PANEL, insertcolor=TEXT)
    s.configure("TNotebook",       background=BG, tabmargins=[2, 4, 0, 0])
    s.configure("TNotebook.Tab",   background=PANEL, foreground=SUBTEXT,
                padding=[16, 6], font=("Segoe UI", 9))
    s.map("TNotebook.Tab",
          background=[("selected", ACCENT)],
          foreground=[("selected", "#ffffff")])
    s.configure("TFrame",      background=BG)
    s.configure("TLabelframe", background=BG, foreground=ACCENT,
                bordercolor=PANEL, relief="solid")
    s.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                font=("Segoe UI", 9, "bold"))
    s.configure("TLabel",      background=BG, foreground=TEXT, font=("Segoe UI", 9))
    s.configure("TEntry",      fieldbackground=ENTRY_BG, foreground=TEXT,
                insertcolor=TEXT, relief="flat")
    s.configure("TButton",     background=BTN_BG, foreground=TEXT,
                font=("Segoe UI", 9), padding=[10, 5], relief="flat")
    s.map("TButton",
          background=[("active", ACCENT), ("pressed", ACCENT2)],
          foreground=[("active", "#ffffff")])
    s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                font=("Segoe UI", 9, "bold"))
    s.map("Accent.TButton",
          background=[("active", ACCENT2), ("disabled", BTN_BG)])
    s.configure("Stop.TButton",  background="#e06c75", foreground="#ffffff",
                font=("Segoe UI", 9, "bold"))
    s.configure("TScrollbar",    background=PANEL, troughcolor=BG, arrowcolor=SUBTEXT)
    s.configure("TCombobox",     fieldbackground=ENTRY_BG, foreground=TEXT,
                selectbackground=ACCENT, selectforeground="#fff")
    s.configure("TSeparator",    background=PANEL)


def _entry_row(parent, label_text: str, var: tk.StringVar,
               show=None, width=40, row=0, col=0) -> ttk.Entry:
    ttk.Label(parent, text=label_text).grid(
        row=row, column=col, sticky="w", padx=(0, 10), pady=4)
    kw = dict(textvariable=var, width=width)
    if show:
        kw["show"] = show
    e = ttk.Entry(parent, **kw)
    e.grid(row=row, column=col+1, sticky="ew", pady=4)
    return e


def _scrollable(parent) -> ttk.Frame:
    """Dikey kaydırmalı iç frame döner."""
    canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
    sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    frame = ttk.Frame(canvas)
    frame.bind("<Configure>", lambda e: canvas.configure(
        scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    def _on_mouse(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mouse)
    return frame


# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mail Otomasyon")
        self.geometry("900x680")
        self.minsize(800, 600)
        self.configure(bg=BG)
        _style(self)

        self.config_data = cfg.load_config()
        self._service = None       # Google Sheets servisi
        self._running = False      # Gönderim devam ediyor mu
        self._stop_flag = False    # Dur komutu

        self._build_ui()
        self._load_config_to_ui()

    # ── UI inşası ────────────────────────────────────────────────────────────

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._nb = nb

        tabs = [
            ("🔗 Bağlantı",   self._tab_connection),
            ("📊 Sütunlar",   self._tab_columns),
            ("✉️ Şablonlar",  self._tab_templates),
            ("⚙️ Ayarlar",    self._tab_settings),
            ("🚀 Gönderim",   self._tab_send),
        ]
        for title, builder in tabs:
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            builder(frame)

    # ── Sekme 1: Bağlantı ────────────────────────────────────────────────────

    def _tab_connection(self, parent):
        f = _scrollable(parent)
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Google Sheets Bağlantısı",
                  font=("Segoe UI", 13, "bold"), foreground=ACCENT).grid(
            row=0, column=0, columnspan=3, pady=(10, 18), sticky="w", padx=10)

        self._v_spreadsheet_id   = tk.StringVar()
        self._v_credentials_file = tk.StringVar()

        _entry_row(f, "Spreadsheet ID:",      self._v_spreadsheet_id,   width=55, row=1)
        _entry_row(f, "Credentials JSON:",    self._v_credentials_file, width=45, row=2)

        ttk.Button(f, text="📁 Dosya Seç",
                   command=self._pick_credentials).grid(
            row=2, column=2, padx=6, pady=4)

        ttk.Separator(f, orient="horizontal").grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=12, padx=10)

        # Sayfa adları
        sheet_lf = ttk.LabelFrame(f, text="Sayfa Adları")
        sheet_lf.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=4)
        sheet_lf.columnconfigure(1, weight=1)

        self._v_sheet_senders    = tk.StringVar()
        self._v_sheet_recipients = tk.StringVar()

        _entry_row(sheet_lf, "Gönderenler sayfası:",  self._v_sheet_senders,    row=0)
        _entry_row(sheet_lf, "Alıcılar sayfası:",     self._v_sheet_recipients, row=1)

        ttk.Button(f, text="🔌 Bağlantıyı Test Et",
                   style="Accent.TButton",
                   command=self._test_connection).grid(
            row=5, column=0, columnspan=3, pady=18, padx=10, sticky="w")

        self._lbl_conn_status = ttk.Label(f, text="", foreground=SUBTEXT)
        self._lbl_conn_status.grid(row=6, column=0, columnspan=3, padx=10, sticky="w")

    def _pick_credentials(self):
        path = filedialog.askopenfilename(
            title="Google credentials.json seç",
            filetypes=[("JSON", "*.json"), ("Tümü", "*.*")])
        if path:
            self._v_credentials_file.set(path)

    def _test_connection(self):
        self._save_to_config()
        self._lbl_conn_status.config(text="⏳ Bağlanılıyor...", foreground=WARNING)
        self.update_idletasks()

        try:
            self._service = sheets.authenticate(
                self.config_data["google_sheets"]["credentials_file"],
                self.config_data["google_sheets"]["token_file"]
            )
            names = sheets.get_sheet_names(
                self._service,
                self.config_data["google_sheets"]["spreadsheet_id"]
            )
            self._lbl_conn_status.config(
                text=f"✅ Bağlantı başarılı! Sayfalar: {', '.join(names)}",
                foreground=SUCCESS)
        except Exception as e:
            self._lbl_conn_status.config(
                text=f"❌ Hata: {e}", foreground=ERROR)

    # ── Sekme 2: Sütunlar ────────────────────────────────────────────────────

    def _tab_columns(self, parent):
        f = _scrollable(parent)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(3, weight=1)

        ttk.Label(f, text="Sütun İsimleri",
                  font=("Segoe UI", 13, "bold"), foreground=ACCENT).grid(
            row=0, column=0, columnspan=4, pady=(10, 18), sticky="w", padx=10)

        # --- Alıcı sütunları ---
        rc_lf = ttk.LabelFrame(f, text="Alıcı Tablosu Sütunları")
        rc_lf.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=6)
        rc_lf.columnconfigure(1, weight=1)
        rc_lf.columnconfigure(3, weight=1)

        rc_fields = [
            ("Kişi Adı:",         "_rc_name"),
            ("Şirket:",           "_rc_company"),
            ("Pozisyon:",         "_rc_position"),
            ("E-posta:",          "_rc_email"),
            ("Son Mail Tarihi:",  "_rc_last_date"),
            ("Mail Sayısı:",      "_rc_mail_count"),
            ("Message-ID:",       "_rc_message_id"),
            ("Datayı Giren:",     "_rc_entered_by"),
            ("Dönüş Durumu:",     "_rc_response"),
            ("Şablon No:",        "_rc_template_no"),
        ]
        for i, (lbl, attr) in enumerate(rc_fields):
            setattr(self, attr, tk.StringVar())
            r, c = divmod(i, 2)
            ttk.Label(rc_lf, text=lbl).grid(
                row=r, column=c*2, sticky="w", padx=8, pady=3)
            ttk.Entry(rc_lf, textvariable=getattr(self, attr), width=22).grid(
                row=r, column=c*2+1, sticky="ew", padx=8, pady=3)

        # --- Gönderici sütunları ---
        sc_lf = ttk.LabelFrame(f, text="Kişi Bilgileri Tablosu Sütunları")
        sc_lf.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=10)
        sc_lf.columnconfigure(1, weight=1)
        sc_lf.columnconfigure(3, weight=1)

        sc_fields = [
            ("İsim:",       "_sc_name"),
            ("Ünvan:",      "_sc_title"),
            ("Gmail:",      "_sc_email"),
            ("App Password:", "_sc_password"),
            ("İmza Linki:", "_sc_signature"),
        ]
        for i, (lbl, attr) in enumerate(sc_fields):
            setattr(self, attr, tk.StringVar())
            r, c = divmod(i, 2)
            ttk.Label(sc_lf, text=lbl).grid(
                row=r, column=c*2, sticky="w", padx=8, pady=3)
            ttk.Entry(sc_lf, textvariable=getattr(self, attr), width=22).grid(
                row=r, column=c*2+1, sticky="ew", padx=8, pady=3)

        ttk.Button(f, text="💾 Sütunları Kaydet",
                   command=self._save_columns).grid(
            row=3, column=0, columnspan=4, pady=14, padx=10, sticky="w")

    def _build_placeholder_hint(self) -> str:
        rc = self.config_data["recipient_columns"]
        sc = self.config_data["sender_columns"]
        vars_ = [rc["name"], rc["company"], rc["position"], rc["entered_by"], sc["title"]]
        placeholders = "  ".join(f"[{v}]" for v in vars_ if v)
        return f"Yer tutucular: {placeholders}\nİmza resmi CID ile otomatik embed edilir."

    def _save_columns(self):
        rc = self.config_data["recipient_columns"]
        rc["name"]        = self._rc_name.get()
        rc["company"]     = self._rc_company.get()
        rc["position"]    = self._rc_position.get()
        rc["email"]       = self._rc_email.get()
        rc["last_date"]   = self._rc_last_date.get()
        rc["mail_count"]  = self._rc_mail_count.get()
        rc["message_id"]  = self._rc_message_id.get()
        rc["entered_by"]  = self._rc_entered_by.get()
        rc["response"]    = self._rc_response.get()
        rc["template_no"] = self._rc_template_no.get()

        sc = self.config_data["sender_columns"]
        sc["name"]      = self._sc_name.get()
        sc["title"]     = self._sc_title.get()
        sc["email"]     = self._sc_email.get()
        sc["password"]  = self._sc_password.get()
        sc["signature"] = self._sc_signature.get()

        cfg.save_config(self.config_data)

        if hasattr(self, "_lbl_placeholder_hint"):
            self._lbl_placeholder_hint.config(text=self._build_placeholder_hint())

        messagebox.showinfo("Kaydedildi", "Sütun isimleri kaydedildi.")

    # ── Sekme 3: Şablonlar ───────────────────────────────────────────────────

    def _tab_templates(self, parent):
        f = _scrollable(parent)
        f.columnconfigure(0, weight=1)

        ttk.Label(f, text="Mail Şablonları",
                  font=("Segoe UI", 13, "bold"), foreground=ACCENT).grid(
            row=0, column=0, columnspan=2, pady=(10, 4), sticky="w", padx=10)

        self._lbl_placeholder_hint = ttk.Label(
            f, text=self._build_placeholder_hint(),
            foreground=SUBTEXT, font=("Segoe UI", 8))
        self._lbl_placeholder_hint.grid(
            row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))

        # Konu
        subj_lf = ttk.LabelFrame(f, text="Mail Konusu")
        subj_lf.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=6)
        subj_lf.columnconfigure(0, weight=1)
        self._v_subject = tk.StringVar()
        ttk.Entry(subj_lf, textvariable=self._v_subject, width=70).pack(
            padx=8, pady=6, fill="x")

        # Şablonlar
        tmpl_names = [
            ("template_1",  "📧 Şablon 1 — İlk Mail"),
            ("template_2",  "📧 Şablon 2 — İkinci Mail"),
            ("template_3",  "📧 Şablon 3 — Üçüncü Mail"),
            ("template_4",  "📧 Şablon 4 — Dördüncü Mail"),
            ("reminder",    "🔔 Hatırlatma Şablonu"),
        ]
        self._tmpl_widgets: dict[str, scrolledtext.ScrolledText] = {}
        for i, (key, title) in enumerate(tmpl_names):
            lf = ttk.LabelFrame(f, text=title)
            lf.grid(row=3+i, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
            lf.columnconfigure(0, weight=1)
            st = scrolledtext.ScrolledText(
                lf, height=6, width=80, bg=ENTRY_BG, fg=TEXT,
                insertbackground=TEXT, relief="flat",
                font=("Consolas", 9))
            st.pack(padx=6, pady=6, fill="both")
            self._tmpl_widgets[key] = st

        # CC / BCC / Ekler
        extra_lf = ttk.LabelFrame(f, text="CC / BCC / Ek Dosyalar")
        extra_lf.grid(row=3+len(tmpl_names), column=0, columnspan=2,
                      sticky="ew", padx=10, pady=10)
        extra_lf.columnconfigure(1, weight=1)

        self._v_cc  = tk.StringVar()
        self._v_bcc = tk.StringVar()
        _entry_row(extra_lf, "CC (virgülle):",  self._v_cc,  width=55, row=0)
        _entry_row(extra_lf, "BCC (virgülle):", self._v_bcc, width=55, row=1)

        # Ekler listesi
        ttk.Label(extra_lf, text="Ekler:").grid(
            row=2, column=0, sticky="nw", padx=(0, 10), pady=4)
        self._att_frame = ttk.Frame(extra_lf)
        self._att_frame.grid(row=2, column=1, sticky="ew", pady=4)
        self._att_vars: list[tk.StringVar] = []
        for _ in range(3):
            self._add_attachment_row()

        ttk.Button(f, text="💾 Şablonları Kaydet",
                   command=self._save_templates).grid(
            row=3+len(tmpl_names)+1, column=0,
            pady=14, padx=10, sticky="w")

    def _add_attachment_row(self):
        v = tk.StringVar()
        row_f = ttk.Frame(self._att_frame)
        row_f.pack(fill="x", pady=2)
        ttk.Entry(row_f, textvariable=v, width=45).pack(side="left")
        ttk.Button(row_f, text="📁",
                   command=lambda var=v: self._pick_file(var)).pack(side="left", padx=4)
        self._att_vars.append(v)

    def _pick_file(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="Ek dosya seç",
            filetypes=[("PDF", "*.pdf"), ("Tümü", "*.*")])
        if path:
            var.set(path)

    def _save_templates(self):
        self.config_data["email"]["subject"] = self._v_subject.get()
        for key, widget in self._tmpl_widgets.items():
            self.config_data["email"]["templates"][key] = widget.get("1.0", tk.END).strip()
        self.config_data["email"]["cc"] = [
            x.strip() for x in self._v_cc.get().split(",") if x.strip()]
        self.config_data["email"]["bcc"] = [
            x.strip() for x in self._v_bcc.get().split(",") if x.strip()]
        self.config_data["email"]["attachments"] = [
            v.get() for v in self._att_vars if v.get().strip()]
        cfg.save_config(self.config_data)
        messagebox.showinfo("Kaydedildi", "Şablonlar kaydedildi.")

    # ── Sekme 4: Ayarlar ─────────────────────────────────────────────────────

    def _tab_settings(self, parent):
        f = _scrollable(parent)
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Gönderim Ayarları",
                  font=("Segoe UI", 13, "bold"), foreground=ACCENT).grid(
            row=0, column=0, columnspan=2, pady=(10, 18), sticky="w", padx=10)

        self._v_wait_sec      = tk.StringVar()
        self._v_reminder_days = tk.StringVar()
        self._v_max_mails     = tk.StringVar()

        fields = [
            ("Gönderici değişiminde bekleme (sn):",
             self._v_wait_sec,
             "Her gönderici hesabı değiştiğinde bu kadar saniye beklenir. (Varsayılan: 180)"),
            ("Hatırlatma için gün sayısı:",
             self._v_reminder_days,
             "Son mailden bu kadar gün geçmişse hatırlatma gönderilir. (Varsayılan: 3)"),
            ("Çalışma başına max mail:",
             self._v_max_mails,
             "Tek çalışmada gönderilebilecek maksimum mail. (Varsayılan: 50)"),
        ]

        for i, (lbl, var, hint) in enumerate(fields):
            ttk.Label(f, text=lbl).grid(
                row=i*2+1, column=0, sticky="w", padx=10, pady=(8, 0))
            ttk.Entry(f, textvariable=var, width=12).grid(
                row=i*2+1, column=1, sticky="w", padx=10, pady=(8, 0))
            ttk.Label(f, text=hint, foreground=SUBTEXT,
                      font=("Segoe UI", 8)).grid(
                row=i*2+2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))

        ttk.Button(f, text="💾 Ayarları Kaydet",
                   command=self._save_settings_tab).grid(
            row=10, column=0, columnspan=2, pady=18, padx=10, sticky="w")

    def _save_settings_tab(self):
        s = self.config_data["settings"]
        try:
            s["wait_seconds_between_senders"] = int(self._v_wait_sec.get())
            s["reminder_after_days"]          = int(self._v_reminder_days.get())
            s["max_mails_per_run"]            = int(self._v_max_mails.get())
            cfg.save_config(self.config_data)
            messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi.")
        except ValueError:
            messagebox.showerror("Hata", "Lütfen sayısal değerler girin.")

    # ── Sekme 5: Gönderim ────────────────────────────────────────────────────

    def _tab_send(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        hdr = ttk.Frame(parent)
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ttk.Label(hdr, text="Toplu Gönderim",
                  font=("Segoe UI", 13, "bold"), foreground=ACCENT).pack(side="left")

        # Durum etiketi
        self._lbl_status = ttk.Label(
            parent, text="Hazır", foreground=SUBTEXT,
            font=("Segoe UI", 10))
        self._lbl_status.grid(row=1, column=0, sticky="w", padx=12, pady=4)

        # Butonlar
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=2, column=0, sticky="w", padx=10, pady=6)

        self._btn_start = ttk.Button(
            btn_frame, text="▶  Gönderimi Başlat",
            style="Accent.TButton",
            command=self._start_send)
        self._btn_start.pack(side="left", padx=(0, 8))

        self._btn_stop = ttk.Button(
            btn_frame, text="⏹  Durdur",
            style="Stop.TButton",
            state="disabled",
            command=self._stop_send)
        self._btn_stop.pack(side="left")

        ttk.Button(
            btn_frame, text="🗑 Logu Temizle",
            command=self._clear_log).pack(side="left", padx=8)

        # Log alanı
        self._log_box = scrolledtext.ScrolledText(
            parent, height=20, state="disabled",
            bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=("Consolas", 9))
        self._log_box.grid(row=3, column=0, sticky="nsew", padx=10, pady=(6, 10))
        parent.rowconfigure(3, weight=1)

        # Renk tag'leri
        self._log_box.tag_config("ok",   foreground=SUCCESS)
        self._log_box.tag_config("warn", foreground=WARNING)
        self._log_box.tag_config("err",  foreground=ERROR)
        self._log_box.tag_config("info", foreground=ACCENT2)

        # Log handler'ı bağla
        self._setup_log_handler()

    def _setup_log_handler(self):
        box = self._log_box

        class UIHandler(logging.Handler):
            def emit(self_, record):
                msg = self_.format(record)
                tag = (
                    "ok"   if "✅" in msg or "gönderildi" in msg.lower() else
                    "err"  if "❌" in msg or "hata" in msg.lower() else
                    "warn" if "⚠️" in msg or "⏳" in msg else
                    "info"
                )
                def _append():
                    box.config(state="normal")
                    box.insert(tk.END, msg + "\n", tag)
                    box.see(tk.END)
                    if int(box.index("end-1c").split(".")[0]) > 2000:
                        box.delete("1.0", "500.0")
                    box.config(state="disabled")
                box.after(0, _append)

        h = UIHandler()
        h.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        h.setLevel(logging.INFO)
        logging.getLogger().addHandler(h)

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", tk.END)
        self._log_box.config(state="disabled")

    def _start_send(self):
        if self._running:
            return
        self._save_to_config()

        if not self._service:
            try:
                self._lbl_status.config(text="⏳ Google Sheets bağlanıyor...", foreground=WARNING)
                self.update_idletasks()
                self._service = sheets.authenticate(
                    self.config_data["google_sheets"]["credentials_file"],
                    self.config_data["google_sheets"]["token_file"]
                )
            except Exception as e:
                self._lbl_status.config(text=f"❌ Bağlantı hatası: {e}", foreground=ERROR)
                return

        self._running   = True
        self._stop_flag = False
        self._btn_start.config(state="disabled")
        self._btn_stop.config(state="normal")
        self._lbl_status.config(text="⏳ Gönderim devam ediyor...", foreground=WARNING)

        def _worker():
            try:
                result = engine.run_bulk_send(
                    config=self.config_data,
                    service=self._service,
                    log_callback=None   # logging handler halleder
                )
                summary = result.summary()
                self.after(0, lambda: self._lbl_status.config(
                    text=f"✅ Tamamlandı — {summary}", foreground=SUCCESS))
            except Exception as e:
                logger.error(f"Gönderim hatası: {e}")
                self.after(0, lambda: self._lbl_status.config(
                    text=f"❌ Hata: {e}", foreground=ERROR))
            finally:
                self._running = False
                self.after(0, lambda: (
                    self._btn_start.config(state="normal"),
                    self._btn_stop.config(state="disabled")
                ))

        threading.Thread(target=_worker, daemon=True).start()

    def _stop_send(self):
        self._stop_flag = True
        self._lbl_status.config(text="⚠️  Durdurma isteği gönderildi...", foreground=WARNING)

    # ── Config ↔ UI senkronizasyonu ──────────────────────────────────────────

    def _load_config_to_ui(self):
        gs = self.config_data["google_sheets"]
        self._v_spreadsheet_id.set(gs.get("spreadsheet_id", ""))
        self._v_credentials_file.set(gs.get("credentials_file", "credentials.json"))

        sn = self.config_data["sheet_names"]
        self._v_sheet_senders.set(sn.get("senders", "Kişi Bilgileri"))
        self._v_sheet_recipients.set(sn.get("recipients", "Alıcı Listesi"))

        rc = self.config_data["recipient_columns"]
        self._rc_name.set(rc.get("name", ""))
        self._rc_company.set(rc.get("company", ""))
        self._rc_position.set(rc.get("position", ""))
        self._rc_email.set(rc.get("email", ""))
        self._rc_last_date.set(rc.get("last_date", ""))
        self._rc_mail_count.set(rc.get("mail_count", ""))
        self._rc_message_id.set(rc.get("message_id", ""))
        self._rc_entered_by.set(rc.get("entered_by", ""))
        self._rc_response.set(rc.get("response", ""))
        self._rc_template_no.set(rc.get("template_no", ""))

        sc = self.config_data["sender_columns"]
        self._sc_name.set(sc.get("name", ""))
        self._sc_title.set(sc.get("title", ""))
        self._sc_email.set(sc.get("email", ""))
        self._sc_password.set(sc.get("password", ""))
        self._sc_signature.set(sc.get("signature", ""))

        em = self.config_data["email"]
        self._v_subject.set(em.get("subject", ""))
        for key, widget in self._tmpl_widgets.items():
            widget.delete("1.0", tk.END)
            widget.insert("1.0", em["templates"].get(key, ""))
        self._v_cc.set(", ".join(em.get("cc", [])))
        self._v_bcc.set(", ".join(em.get("bcc", [])))
        for i, path in enumerate(em.get("attachments", [])):
            if i < len(self._att_vars):
                self._att_vars[i].set(path)

        s = self.config_data["settings"]
        self._v_wait_sec.set(str(s.get("wait_seconds_between_senders", 180)))
        self._v_reminder_days.set(str(s.get("reminder_after_days", 3)))
        self._v_max_mails.set(str(s.get("max_mails_per_run", 50)))

    def _save_to_config(self):
        """UI'daki tüm değerleri config_data'ya yazar ve diske kaydeder."""
        gs = self.config_data["google_sheets"]
        gs["spreadsheet_id"]   = self._v_spreadsheet_id.get().strip()
        gs["credentials_file"] = self._v_credentials_file.get().strip()

        sn = self.config_data["sheet_names"]
        sn["senders"]    = self._v_sheet_senders.get().strip()
        sn["recipients"] = self._v_sheet_recipients.get().strip()

        # Sütunlar
        self._save_columns()

        # Şablonlar
        em = self.config_data["email"]
        em["subject"] = self._v_subject.get()
        for key, widget in self._tmpl_widgets.items():
            em["templates"][key] = widget.get("1.0", tk.END).strip()
        em["cc"]  = [x.strip() for x in self._v_cc.get().split(",")  if x.strip()]
        em["bcc"] = [x.strip() for x in self._v_bcc.get().split(",") if x.strip()]
        em["attachments"] = [v.get() for v in self._att_vars if v.get().strip()]

        # Ayarlar
        s = self.config_data["settings"]
        try:
            s["wait_seconds_between_senders"] = int(self._v_wait_sec.get())
            s["reminder_after_days"]          = int(self._v_reminder_days.get())
            s["max_mails_per_run"]            = int(self._v_max_mails.get())
        except ValueError:
            pass

        cfg.save_config(self.config_data)


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler("mail_otomasyon.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    app = App()
    app.mainloop()
