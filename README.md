# edu-radar

Notifikasi otomatis info SMA dan pra-kuliah (SNPMB, UTBK-SNBT, SNBP, KIP Kuliah, PTKIN, kebijakan, PTN) ke Discord. Target: tahu dalam kurang dari 3 jam setelah ada kabar.

Lanjut dari sesi lain? Baca `HANDOFF.md` dulu.

## Cara kerja
- `main.py` baca `sources.yml`, ambil semua sumber paralel, kirim yang baru ke Discord.
- Semua sumber dicek tiap run (15 menit). `every` per sumber opsional.
- Cek `robots.txt` per host. Dilarang = sumber dilewati dan masuk alert sistem.
- Run pertama per sumber = seed: tandai item lama, tidak kirim notif.
- Kirim ke Discord gagal = item tidak ditandai, dicoba lagi run berikutnya.
- Sumber gagal atau kosong 3x berturut-turut: alert #sistem. Pulih: pesan pulih.
- State di branch `state` (1 commit, force push). Riwayat `main` bersih.

## Channel Discord
- `#resmi`: label RESMI dan PTN. Semua perubahan dikirim.
- `#berita`: label BERITA. Hanya yang lolos filter.
- `#sistem`: sumber rusak atau pulih.

## Setup
1. Buat repo publik, upload semua file.
2. Buat 3 webhook Discord (Server Settings > Integrations > Webhooks).
3. Repo > Settings > Secrets and variables > Actions, tambah:
   - `DISCORD_WEBHOOK_RESMI`
   - `DISCORD_WEBHOOK_BERITA`
   - `DISCORD_WEBHOOK_SISTEM`
   - `HC_URL` (opsional, URL ping healthchecks.io)
4. Repo > Settings > Actions > General > Workflow permissions: Read and write.
5. Jalankan manual sekali: Actions > edu-radar > Run workflow (seed, tanpa notif).
6. Pemicu utama (cron GitHub sering telat):
   - cron-job.org, tiap 15 menit, POST `https://api.github.com/repos/USER/REPO/actions/workflows/run.yml/dispatches`
   - Header: `Authorization: Bearer TOKEN`, `Accept: application/vnd.github+json`
   - Body: `{"ref":"main"}`
   - TOKEN = fine-grained PAT, izin Actions: write, hanya repo ini.
7. healthchecks.io: period 30 menit, grace 30 menit. Mati = email.

## Tambah atau ubah sumber
Edit `sources.yml`. Tidak perlu ubah kode.
- RSS: `type: rss`, `filter: edu` (longgar) atau `strict` (induk/nasional).
- Halaman: `type: page`. `mode: links` untuk daftar tautan. `ignore_regex` buang baris dinamis.
- PTN baru: dua entri per kampus (jadwal text, pengumuman links), `label: PTN`.
- Belum siap: `enabled: false` dan isi `todo`.
- Path bertahun (UGM `v26`, UNNES `2026`) diganti tiap musim.

## Tes lokal
```
pip install -r requirements.txt
DRY_RUN=1 STATE_PATH=/tmp/s.json python main.py          # seed
DRY_RUN=1 STATE_PATH=/tmp/s.json FORCE=1 python main.py   # abaikan every
DRY_RUN=1 ONLY=rss-antara python main.py                  # satu sumber
SKIP_ROBOTS=1 ...                                          # hanya tes lokal
```

## Catatan
- Kompas, Tribunnews, TKA, pusmendik, UNJ tidak dipantau (RSS dilarang, mati, atau robots melarang).
- 7 PTN masih nonaktif sampai URL-nya terbaca: lihat `todo` di `sources.yml`.
- UGM v27: alert muncul saat halaman ada. Situs yang membalas 200 untuk semua path bisa memicu alarm palsu.
