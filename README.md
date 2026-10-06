# Riftroam Bio Tracker updater

Free hosted automation refreshes the VALORANT accounts saved on published Bio pages.
Users manage accounts entirely on the website. No desktop application is needed.

The website starts this workflow when source data is unavailable. A five-minute
schedule also refreshes accounts without visitors. GitHub can delay scheduled jobs;
the website keeps the last successful snapshot and polls while an update is queued.

The updater uses browser-compatible HTTP, validates source responses and sends
upstream JSON to the Bio Worker. The Worker validates the saved Riot ID, strips
private identifiers and stores only the public rank and ten recent matches.
Access failures never overwrite a successful snapshot.

## Deployment

Store the same random secret as `PROFILE_SYNC_KEY` in GitHub Actions and
`VALORANT_REFRESH_KEY` in the Bio Worker. The Worker also uses the server-only
`VALORANT_GITHUB_TOKEN` to dispatch `sync.yml`. Secrets, account lists and profile
data are never committed to this repository.

This repository is public so standard GitHub-hosted Linux runners use the free
public-repository allowance. It does not use paid runners or a rented server.
