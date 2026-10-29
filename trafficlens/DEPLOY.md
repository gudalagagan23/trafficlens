# Put TrafficLens online (your own live Streamlit link)

You will do three things: create an empty GitHub repo, push this folder to it, then point Streamlit at it.
Your GitHub login and Streamlit login happen in YOUR browser. Never paste a password or token anywhere else.

## 1. Create an empty repo on GitHub
1. Open https://github.com/new (signed in as `gudalagagan23`).
2. Repository name: `trafficlens`
3. Choose **Public** (simplest for the free Streamlit tier).
4. Do **not** tick "Add a README" or any other starter file. Click **Create repository**.

## 2. Push this folder to it
Open the `trafficlens` folder in VS Code, open a terminal (Terminal > New Terminal) and run:

```
git init
git add .
git commit -m "TrafficLens"
git branch -M main
git remote add origin https://github.com/gudalagagan23/trafficlens.git
git push -u origin main
```

A browser window opens asking you to sign in to GitHub. Approve it. That is the authentication step.

- No `git`? Install it from https://git-scm.com, then reopen VS Code.
- Prefer clicking? In VS Code open **Source Control** > **Publish to GitHub** > name it `trafficlens` > Public.

Check https://github.com/gudalagagan23/trafficlens: you should see `streamlit_app.py`, `data/`, `outputs/` and the other folders.

## 3. Deploy on Streamlit
1. Open https://share.streamlit.io and sign in with GitHub.
2. Click **Create app** (or **New app**) and choose to deploy from an existing GitHub repo.
3. Repository: `gudalagagan23/trafficlens`   Branch: `main`   **Main file path: `streamlit_app.py`**
4. Open **Advanced settings** and pick **Python 3.12** (3.11 also works). This project was tested on 3.12.
5. Optional: choose your own web address, for example `trafficlens-gagan`.
6. Click **Deploy**. The first build takes a few minutes. Your link will look like
   `https://trafficlens-gagan.streamlit.app` (or the address Streamlit gives you).

## If something goes wrong
- **Build error or "module not found":** open **Manage app** > logs. `requirements.txt` is installed automatically.
- **"No results yet":** the `outputs/` and `data/` folders were not pushed. Run `git add . && git commit -m fix && git push`.
- **Very old Python selected:** change it in Advanced settings and redeploy.

## Updating later
Change anything, run `python run_all.py` if you want new results, then:
```
git add .
git commit -m "update"
git push
```
The app redeploys by itself.

## What "live" means here
The dashboard replays 21 simulated days (use the sidebar slider). It is not connected to a real website's traffic.
To collect real visits see the "Use your own data later" section of README.md.
