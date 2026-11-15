"""Pemantau Learning Management System SMA Negeri 22 Makassar.

Dijalankan GitHub Actions setiap sekitar 5 menit dari luar jaringan sekolah.
Pesan Telegram hanya dikirim saat status berubah (mati atau pulih), ditambah
pengingat setiap 6 jam selama LMS masih mati. Status terakhir disimpan di
status.json, supaya pesan tidak dikirim berulang-ulang.

Rahasia (token bot dan chat id) dibaca dari variabel lingkungan yang diisi
GitHub Secrets, tidak pernah ditulis di file ini.
"""
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

URL = os.environ.get("URL_LMS", "https://lms-sman22mks.my.id/masuk/")
BERKAS = os.environ.get("BERKAS_STATUS", "status.json")
WITA = dt.timezone(dt.timedelta(hours=8), "WITA")
PERCOBAAN = 3                                   # dianggap mati setelah 3 kali gagal berturut-turut
JEDA = int(os.environ.get("JEDA_DETIK", "20"))  # jeda antar percobaan
PENGINGAT_JAM = 6


def cek_sekali():
    """Kembalikan (berhasil, alasan)."""
    req = urllib.request.Request(URL, headers={"User-Agent": "Pemantau-LMS-SMAN22/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        isi = e.read(4000).decode("utf-8", "ignore")
        m = re.search(r"[Ee]rror code:?\s*(\d{3,4})", isi)
        return False, f"HTTP {e.code}" + (f", Cloudflare {m.group(1)}" if m else "")
    except Exception as e:  # waktu habis, DNS, koneksi ditolak, dll.
        return False, f"{type(e).__name__}: {str(e)[:120]}"


def cek():
    alasan = ""
    for i in range(PERCOBAAN):
        berhasil, alasan = cek_sekali()
        if berhasil:
            return True, alasan
        if i < PERCOBAAN - 1:
            time.sleep(JEDA)
    return False, alasan


def jelaskan(alasan):
    if "1033" in alasan or "HTTP 530" in alasan:
        return ("Cloudflare tidak tersambung ke server sekolah. Kemungkinan komputer atau VM mati, "
                "internet sekolah putus, atau layanan tunnel (cloudflared) berhenti.")
    if "HTTP 502" in alasan or "HTTP 503" in alasan:
        return "Server menyala, tetapi layanan LMS (lms.service) berhenti atau sedang dimulai ulang."
    if "HTTP 504" in alasan or "timed out" in alasan.lower() or "Timeout" in alasan:
        return "Server tidak menjawab dalam 20 detik. Kemungkinan sedang sangat sibuk atau macet."
    return "Penyebab belum dikenali; lihat keterangan teknis di bawah."


def durasi(detik):
    menit = int(detik // 60)
    jam, menit = divmod(menit, 60)
    hari, jam = divmod(jam, 24)
    bagian = [f"{hari} hari" if hari else "", f"{jam} jam" if jam else "", f"{menit} menit"]
    return " ".join(b for b in bagian if b)


def waktu(t):
    return t.astimezone(WITA).strftime("%d-%m-%Y %H.%M WITA")


def kirim(teks):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[Telegram belum diatur, pesan hanya ditampilkan]\n" + teks)
        return
    data = urllib.parse.urlencode({"chat_id": chat.strip(), "text": teks}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token.strip()}/sendMessage", data=data, timeout=20)
    except urllib.error.HTTPError as e:
        try:
            alasan = json.loads(e.read().decode("utf-8", "ignore")).get("description", "")
        except ValueError:
            alasan = ""
        petunjuk = {
            401: "Token bot salah. Periksa Secret TELEGRAM_TOKEN.",
            400: "Chat ID salah atau bot belum pernah di-Start. Periksa Secret TELEGRAM_CHAT_ID (angka saja).",
            403: "Bot diblokir atau belum di-Start di Telegram. Buka bot lalu tekan Start.",
        }.get(e.code, "Periksa kembali Secret TELEGRAM_TOKEN dan TELEGRAM_CHAT_ID.")
        raise SystemExit(f"GAGAL MENGIRIM KE TELEGRAM (HTTP {e.code}: {alasan}). {petunjuk}")


def baca_status(sekarang):
    try:
        with open(BERKAS, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"status": "up", "sejak": sekarang.isoformat(timespec="seconds")}


def main():
    sekarang = dt.datetime.now(WITA)
    lama = baca_status(sekarang)
    berhasil, alasan = cek()
    baru = "up" if berhasil else "down"
    tulis = False

    if os.environ.get("UJI") == "true":
        kirim(f"Bot pemantau Learning Management System terhubung.\n"
              f"Status sekarang: {'NORMAL' if berhasil else 'TIDAK BISA DIAKSES'} ({alasan}).")

    if baru != lama.get("status"):
        if baru == "down":
            kirim(f"\U0001F534 Learning Management System TIDAK BISA DIAKSES\n"
                  f"Sejak: {waktu(sekarang)}\n\n{jelaskan(alasan)}\n\nKeterangan teknis: {alasan}\n{URL}")
            lama = {"status": "down", "sejak": sekarang.isoformat(timespec="seconds"), "alasan": alasan,
                    "diingatkan": sekarang.isoformat(timespec="seconds")}
        else:
            mulai = dt.datetime.fromisoformat(lama["sejak"])
            kirim(f"\U0001F7E2 Learning Management System kembali normal\n"
                  f"Pulih: {waktu(sekarang)}\nTadi tidak bisa diakses selama {durasi((sekarang - mulai).total_seconds())}.")
            lama = {"status": "up", "sejak": sekarang.isoformat(timespec="seconds")}
        tulis = True
    elif baru == "down":
        diingatkan = dt.datetime.fromisoformat(lama.get("diingatkan", lama["sejak"]))
        if sekarang - diingatkan >= dt.timedelta(hours=PENGINGAT_JAM):
            mulai = dt.datetime.fromisoformat(lama["sejak"])
            kirim(f"\U0001F7E0 Pengingat: Learning Management System masih tidak bisa diakses\n"
                  f"Sudah {durasi((sekarang - mulai).total_seconds())} (sejak {waktu(mulai)}).\n"
                  f"Keterangan teknis: {alasan}")
            lama["diingatkan"] = sekarang.isoformat(timespec="seconds")
            tulis = True

    # GitHub mematikan jadwal di repositori publik yang 60 hari tanpa aktivitas,
    # jadi status ditulis ulang paling lambat setiap 30 hari.
    ditulis = dt.datetime.fromisoformat(lama.get("ditulis", "2000-01-01T00:00:00+08:00"))
    if sekarang - ditulis >= dt.timedelta(days=30):
        tulis = True

    if tulis:
        lama["ditulis"] = sekarang.isoformat(timespec="seconds")
        with open(BERKAS, "w", encoding="utf-8") as f:
            json.dump(lama, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print(f"{baru} | {alasan} | status.json {'diperbarui' if tulis else 'tetap'}")
    keluaran = os.environ.get("GITHUB_OUTPUT")
    if keluaran:
        with open(keluaran, "a", encoding="utf-8") as f:
            f.write(f"tulis={'1' if tulis else '0'}\nstatus={baru}\n")


if __name__ == "__main__":
    # Penyebab galat ditulis sebagai catatan GitHub (::error::) supaya terbaca di halaman Actions.
    # Isinya tidak pernah memuat token atau chat id.
    try:
        main()
    except SystemExit as e:
        if e.code not in (0, None):
            print(f"::error::{e.code}")
        raise
    except Exception as e:
        print(f"::error::{type(e).__name__}: {e}")
        raise
