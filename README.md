# Pemantau Learning Management System SMA Negeri 22 Makassar

GitHub Actions membuka https://lms-sman22mks.my.id/masuk/ setiap sekitar 5 menit dari luar jaringan sekolah.
Jika gagal 3 kali berturut-turut, bot Telegram mengirim pesan "TIDAK BISA DIAKSES" beserta perkiraan penyebabnya.
Saat pulih, bot mengirim pesan "kembali normal" beserta lama gangguan. Selama masih mati, pengingat dikirim setiap 6 jam.

- `cek.py` memeriksa situs dan mengirim pesan.
- `.github/workflows/pantau.yml` adalah jadwalnya.
- `status.json` menyimpan status terakhir. File ini diperbarui otomatis, jangan diubah manual.

Token bot dan chat id disimpan sebagai **GitHub Secrets** (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`), tidak pernah di dalam kode.

Uji kirim pesan: tab **Actions** → **Pantau LMS** → **Run workflow**.
