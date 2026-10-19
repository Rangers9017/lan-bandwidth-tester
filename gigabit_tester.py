import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import time
import struct
import os

# ─────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────
DEFAULT_PORT = 5201
CHUNK_SIZE   = 65536       # 64 KB bloklar
TEST_DURATION = 10         # saniye
GIGABIT      = 1_000_000_000

# ─────────────────────────────────────────────
#  Sunucu (Server) mantığı
# ─────────────────────────────────────────────
class SpeedServer:
    def __init__(self, port, log_cb, result_cb):
        self.port      = port
        self.log       = log_cb
        self.result    = result_cb
        self._running  = False
        self._thread   = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _listen(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        try:
            srv.bind(("", self.port))
            srv.listen(1)
            srv.settimeout(1.0)
            self.log(f"Sunucu dinleniyor: port {self.port}")
            while self._running:
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                self.log(f"Bağlantı kabul edildi: {addr[0]}")
                self._handle(conn)
        except Exception as e:
            self.log(f"Sunucu hatası: {e}")
        finally:
            srv.close()
            self.log("Sunucu durduruldu.")

    def _handle(self, conn):
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        total = 0
        t0    = None
        try:
            while True:
                data = conn.recv(CHUNK_SIZE)
                if not data:
                    break
                if t0 is None:
                    t0 = time.perf_counter()
                total += len(data)
        except Exception:
            pass
        finally:
            conn.close()

        if t0:
            elapsed = time.perf_counter() - t0
            mbps    = (total * 8) / elapsed / 1e6
            gbps    = mbps / 1000
            self.log(f"Alındı: {total/1e6:.1f} MB  |  Süre: {elapsed:.2f}s")
            self.result(mbps, gbps, elapsed, total)

# ─────────────────────────────────────────────
#  İstemci (Client) mantığı
# ─────────────────────────────────────────────
class SpeedClient:
    def __init__(self, ip, port, duration, log_cb, progress_cb, result_cb):
        self.ip          = ip
        self.port        = port
        self.duration    = duration
        self.log         = log_cb
        self.progress    = progress_cb
        self.result      = result_cb
        self._running    = False
        self._thread     = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        payload = os.urandom(CHUNK_SIZE)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
            s.connect((self.ip, self.port))
            self.log(f"Bağlandı: {self.ip}:{self.port}")
        except Exception as e:
            self.log(f"Bağlantı hatası: {e}")
            self.result(None, None, None, None)
            return

        total   = 0
        t0      = time.perf_counter()
        t_last  = t0
        sent_interval = 0

        try:
            while self._running:
                now = time.perf_counter()
                elapsed = now - t0
                if elapsed >= self.duration:
                    break
                s.sendall(payload)
                total         += len(payload)
                sent_interval += len(payload)

                # Her 0.3 saniyede hız güncelle
                if now - t_last >= 0.3:
                    instant_mbps = (sent_interval * 8) / (now - t_last) / 1e6
                    self.progress(elapsed, self.duration, instant_mbps)
                    t_last        = now
                    sent_interval = 0
        except Exception as e:
            self.log(f"Gönderim hatası: {e}")
        finally:
            s.close()

        elapsed = time.perf_counter() - t0
        mbps    = (total * 8) / elapsed / 1e6
        gbps    = mbps / 1000
        self.log(f"Gönderildi: {total/1e6:.1f} MB  |  Süre: {elapsed:.2f}s")
        self.result(mbps, gbps, elapsed, total)

# ─────────────────────────────────────────────
#  GUI
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gigabit Hız Testi")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self._server  = None
        self._client  = None

        self._build_ui()

    # ── UI İnşası ───────────────────────────
    def _build_ui(self):
        PAD  = {"padx": 12, "pady": 6}
        BG   = "#1e1e2e"
        FG   = "#cdd6f4"
        ENT  = "#313244"
        ACC  = "#89b4fa"
        GRN  = "#a6e3a1"
        RED  = "#f38ba8"
        YLW  = "#f9e2af"

        self._bg  = BG
        self._fg  = FG
        self._acc = ACC
        self._grn = GRN
        self._red = RED
        self._ylw = YLW

        # ── Başlık
        tk.Label(self, text="⚡ Gigabit Hız Testi",
                 font=("Segoe UI", 16, "bold"),
                 bg=BG, fg=ACC).pack(pady=(18, 4))
        tk.Label(self, text="İki bilgisayar arasındaki Ethernet bant genişliğini ölçer",
                 font=("Segoe UI", 9), bg=BG, fg="#6c7086").pack()

        # ── Mod seçimi
        mode_fr = tk.Frame(self, bg=BG)
        mode_fr.pack(fill="x", padx=20, pady=6)
        tk.Label(mode_fr, text="Mod:", font=("Segoe UI", 10, "bold"),
                 bg=BG, fg=FG, width=10, anchor="w").grid(row=0, column=0)
        self._mode = tk.StringVar(value="client")
        tk.Radiobutton(mode_fr, text="İstemci (hız gönder)",
                       variable=self._mode, value="client",
                       command=self._on_mode_change,
                       bg=BG, fg=FG, selectcolor=ENT,
                       activebackground=BG, font=("Segoe UI", 10)).grid(row=0, column=1, padx=6)
        tk.Radiobutton(mode_fr, text="Sunucu (hız al)",
                       variable=self._mode, value="server",
                       command=self._on_mode_change,
                       bg=BG, fg=FG, selectcolor=ENT,
                       activebackground=BG, font=("Segoe UI", 10)).grid(row=0, column=2, padx=6)

        # ── Ayarlar çerçevesi
        cfg_fr = tk.LabelFrame(self, text=" Ayarlar ", font=("Segoe UI", 9),
                               bg=BG, fg=ACC, bd=1, relief="groove")
        cfg_fr.pack(fill="x", padx=20, pady=6)

        def lbl(parent, text, row):
            tk.Label(parent, text=text, font=("Segoe UI", 10),
                     bg=BG, fg=FG, width=12, anchor="w").grid(
                         row=row, column=0, padx=10, pady=4, sticky="w")

        def ent(parent, row, default, width=22):
            e = tk.Entry(parent, font=("Segoe UI", 10),
                         bg=ENT, fg=FG, insertbackground=FG,
                         relief="flat", width=width)
            e.grid(row=row, column=1, padx=10, pady=4, sticky="w")
            e.insert(0, default)
            return e

        lbl(cfg_fr, "Hedef IP:", 0)
        self._ip_entry = ent(cfg_fr, 0, "192.168.1.100")

        lbl(cfg_fr, "Port:", 1)
        self._port_entry = ent(cfg_fr, 1, str(DEFAULT_PORT), width=8)

        lbl(cfg_fr, "Süre (sn):", 2)
        self._dur_entry = ent(cfg_fr, 2, str(TEST_DURATION), width=8)

        # ── Durum / IP bilgisi
        self._my_ip_var = tk.StringVar()
        self._update_my_ip()
        tk.Label(cfg_fr, textvariable=self._my_ip_var,
                 font=("Segoe UI", 9, "italic"),
                 bg=BG, fg="#6c7086").grid(row=3, columnspan=2, pady=(2, 6))

        # ── İlerleme çubuğu
        prog_fr = tk.Frame(self, bg=BG)
        prog_fr.pack(fill="x", padx=20, pady=(4, 0))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor="#313244",
                        background="#89b4fa",
                        bordercolor="#1e1e2e",
                        darkcolor="#89b4fa",
                        lightcolor="#89b4fa")

        self._progress = ttk.Progressbar(prog_fr, orient="horizontal",
                                         length=440, mode="determinate",
                                         style="Custom.Horizontal.TProgressbar")
        self._progress.pack(fill="x")

        self._progress_label = tk.Label(self, text="",
                                        font=("Segoe UI", 9),
                                        bg=BG, fg=YLW)
        self._progress_label.pack()

        # ── Anlık hız göstergesi
        self._speed_var = tk.StringVar(value="─")
        tk.Label(self, textvariable=self._speed_var,
                 font=("Segoe UI", 28, "bold"),
                 bg=BG, fg=ACC).pack(pady=(8, 0))
        tk.Label(self, text="Mbit/s (anlık)",
                 font=("Segoe UI", 9), bg=BG, fg="#6c7086").pack()

        # ── Sonuç kutusu
        res_fr = tk.Frame(self, bg="#181825", bd=1, relief="sunken")
        res_fr.pack(fill="x", padx=20, pady=10)
        for i, (lbl_txt, var_attr, color) in enumerate([
            ("Ortalama Hız", "_res_avg", ACC),
            ("Toplam Veri",  "_res_data", FG),
            ("Süre",         "_res_time", FG),
            ("Gigabit?",     "_res_gig",  GRN),
        ]):
            setattr(self, var_attr, tk.StringVar(value="─"))
            c = tk.Frame(res_fr, bg="#181825")
            c.grid(row=0, column=i, padx=18, pady=8)
            tk.Label(c, text=lbl_txt, font=("Segoe UI", 8),
                     bg="#181825", fg="#6c7086").pack()
            tk.Label(c, textvariable=getattr(self, var_attr),
                     font=("Segoe UI", 11, "bold"),
                     bg="#181825", fg=color).pack()

        # ── Butonlar
        btn_fr = tk.Frame(self, bg=BG)
        btn_fr.pack(pady=(4, 8))

        def btn(parent, text, cmd, col, fg_c):
            b = tk.Button(parent, text=text, command=cmd,
                          font=("Segoe UI", 10, "bold"),
                          bg=ENT, fg=fg_c, activebackground="#45475a",
                          relief="flat", padx=20, pady=6, cursor="hand2")
            b.grid(row=0, column=col, padx=8)
            return b

        self._start_btn = btn(btn_fr, "▶  Başlat", self._start, 0, GRN)
        self._stop_btn  = btn(btn_fr, "■  Durdur", self._stop,  1, RED)
        self._stop_btn.config(state="disabled")

        # ── Log alanı
        log_fr = tk.LabelFrame(self, text=" Log ", font=("Segoe UI", 9),
                                bg=BG, fg=ACC, bd=1, relief="groove")
        log_fr.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        self._log_text = tk.Text(log_fr, height=7, font=("Consolas", 9),
                                 bg="#181825", fg="#a6adc8",
                                 insertbackground=FG, relief="flat",
                                 state="disabled")
        sc = ttk.Scrollbar(log_fr, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)

        self._on_mode_change()

    # ── Yardımcılar ─────────────────────────
    def _update_my_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "bilinmiyor"
        self._my_ip_var.set(f"Bu bilgisayarın IP'si: {ip}")

    def _on_mode_change(self):
        is_client = self._mode.get() == "client"
        state = "normal" if is_client else "disabled"
        self._ip_entry.config(state=state)
        self._dur_entry.config(state=state)

    def _log(self, msg):
        def _write():
            self._log_text.config(state="normal")
            self._log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self.after(0, _write)

    def _set_progress(self, elapsed, total_dur, instant_mbps):
        pct = min(100, (elapsed / total_dur) * 100)
        def _upd():
            self._progress["value"] = pct
            self._progress_label.config(
                text=f"{elapsed:.1f}s / {total_dur}s  ({pct:.0f}%)")
            self._speed_var.set(f"{instant_mbps:,.0f}")
        self.after(0, _upd)

    def _show_result(self, mbps, gbps, elapsed, total_bytes):
        def _upd():
            self._progress["value"] = 0
            self._progress_label.config(text="")
            if mbps is None:
                self._res_avg.set("─")
                self._res_data.set("─")
                self._res_time.set("─")
                self._res_gig.set("─")
                self._speed_var.set("─")
            else:
                self._res_avg.set(f"{mbps:,.1f} Mbit/s")
                self._res_data.set(f"{total_bytes/1e6:.1f} MB")
                self._res_time.set(f"{elapsed:.2f} s")
                is_gig = mbps >= 800   # ~%80 gigabit kabul
                self._res_gig.set("✔  EVET" if is_gig else "✘  HAYIR")
                color = self._grn if is_gig else self._red
                # renk güncelle
                for w in self.winfo_children():
                    if isinstance(w, tk.Frame):
                        for fr in w.winfo_children():
                            if isinstance(fr, tk.Frame):
                                for lbl in fr.winfo_children():
                                    if isinstance(lbl, tk.Label) and \
                                       lbl.cget("textvariable") == str(self._res_gig):
                                        lbl.config(fg=color)
                self._speed_var.set(f"{mbps:,.0f}")
                self._log(
                    f"{'✔ Gigabit MEVCUT' if is_gig else '✘ Gigabit YOK'} — "
                    f"Ortalama: {mbps:.1f} Mbit/s  ({gbps:.3f} Gbit/s)")
            self._start_btn.config(state="normal")
            self._stop_btn.config(state="disabled")
        self.after(0, _upd)

    # ── Başlat / Durdur ─────────────────────
    def _start(self):
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        # sıfırla
        for attr in ("_res_avg", "_res_data", "_res_time", "_res_gig"):
            getattr(self, attr).set("─")
        self._speed_var.set("─")
        self._progress["value"] = 0

        port = int(self._port_entry.get().strip() or DEFAULT_PORT)

        if self._mode.get() == "server":
            self._server = SpeedServer(port, self._log, self._show_result)
            self._server.start()
        else:
            ip  = self._ip_entry.get().strip()
            dur = int(self._dur_entry.get().strip() or TEST_DURATION)
            if not ip:
                messagebox.showerror("Hata", "Hedef IP giriniz.")
                self._start_btn.config(state="normal")
                self._stop_btn.config(state="disabled")
                return
            self._log(f"Test başlıyor → {ip}:{port}  ({dur}s)")
            self._client = SpeedClient(ip, port, dur,
                                       self._log,
                                       self._set_progress,
                                       self._show_result)
            self._client.start()

    def _stop(self):
        if self._server:
            self._server.stop()
            self._server = None
        if self._client:
            self._client.stop()
            self._client = None
        self._log("Durduruldu.")
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")

# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()

