# Getting started: Shanumkha Invoices & Stock

These steps set up the app on **one computer**. It takes about 15 minutes the first time.
Everything is done with double-clicks; you don't need to type commands.

---

## Step 1: Install Python (one time only)

Python is the free engine the app runs on.

1. Open **https://www.python.org/downloads/** in your browser.
2. Click the yellow **Download Python 3.x** button (any version 3.10 or newer is fine).
3. Open the downloaded file.
4. **Windows: on the first screen, tick ☑ "Add python.exe to PATH"** at the bottom. This is important.
5. Click **Install Now** and wait until it says *Setup was successful*. Close the installer.

*(Mac: open the downloaded .pkg file and click Continue → Install.)*

## Step 2: Put the app folder on your computer

1. Find the downloaded **Shanumkha-Invoices.zip** (usually in *Downloads*).
2. **Windows:** right-click it → **Extract All…** → choose **Documents** → **Extract**.
   **Mac:** double-click the zip, then drag the **Shanumkha-Invoices** folder into **Documents**.
3. You now have a folder **Documents\Shanumkha-Invoices**. Don't run the app from inside the zip.

> Your data will be saved inside this folder (in the `instance` folder). Don't delete it.

## Step 3: Start the app

**Windows:** open the folder and double-click **Start-Windows.bat**.

- If a blue box says *"Windows protected your PC"*: click **More info** → **Run anyway**.
  (It appears because the file is new to Windows, not because it is unsafe.)
- A black window opens. **The first time it prepares the app for 1–3 minutes (internet needed).**
- Your browser then opens the app at **http://127.0.0.1:5000**.

**Mac:** double-click **Start-Mac.command**. The first time, macOS says *"Apple could not verify
'Start-Mac.command'…"*. Click **Done** (not "Move to Bin"), then either:

- open ** → System Settings → Privacy & Security**, scroll down, click **Open Anyway**, enter your Mac
  password and click **Open Anyway** again, **or**
- open **Terminal** (⌘ Space, type Terminal) and paste this line, then press Enter. It unblocks both Mac files at once:
  `xattr -dr com.apple.quarantine ~/Documents/Shanumkha-Invoices && bash ~/Documents/Shanumkha-Invoices/Start-Mac.command`

This warning appears for any app not from the App Store; it only has to be allowed once.

> **Keep the black window open while you use the app.** Closing it stops the app.
> To start again tomorrow, double-click **Start-Windows.bat** again (it will be fast after the first time).
> If the browser didn't open, open it yourself and go to **http://127.0.0.1:5000**.

## Step 4: Create the administrator login (first time only)

The first page asks you to **create the administrator**. Enter your name, a username and a password
(at least 8 characters). **Write the password down somewhere safe.**

## Step 5: Enter your business details

Click **Settings** in the menu and fill in your business name, address, GSTIN, phone, bank/UPI details and
terms. Check the invoice prefix (**SCP**) and the default payment due days. Click **Save settings**.
These details print on every invoice.

## Step 6: Add logins for your team

Click **Users & access** → **+ Add user** for each person (partners, investors, staff):

1. Enter their name, a username and a starting password.
2. Choose a **Role**. This fills in suggested access.
3. In **Access to each section**, set each section to *No access*, *View only* or *View & edit*.
4. Click **Save**. Give them their username and password; they can change the password under **My account**.

## Step 7: Add your products and stock

Either:

- **Products** → **+ Add product** for each item (name, code, HSN, UOM, price, GST %, opening stock,
  reorder level), **or**
- **Products** → **Upload stock file** and choose a PDF, Excel or Word purchase bill / stock list.
  Check the preview and click **Update stock**. The file `samples/stock-upload-template.xlsx` shows a
  simple layout you can fill in.

## Step 8: Add customers and make your first invoice

1. **Customers** → **+ Add customer** (name, address, mail ID, phone, city).
2. Click **+ New invoice**, choose the customer, add items, set **Payment due (days)**, then **Save invoice**.
3. Click **Print / Save PDF** to print it or save it as a PDF. It then appears under **Dispatch**.

## Step 9: Make it an app with its own icon (optional)

With the app running, install it so it opens in its own window with an icon, like any other app:

- **Google Chrome or Microsoft Edge (Windows or Mac):** open **http://127.0.0.1:5000**, then click the
  **install icon** at the right end of the address bar (a small screen with a down arrow) → **Install**.
  Or use the **⋮** menu → **Cast, save and share** → **Install page as app** (Edge: **⋯** → **Apps** →
  **Install this site as an app**).
- **Safari on Mac:** open **http://127.0.0.1:5000**, then **File → Add to Dock** → **Add**.

The **Shanumkha Invoices** icon then appears in your Dock / Start menu / desktop. Click it to open the app.

> The app still needs its black (Terminal) window running in the background. If you click the icon while it
> isn't running, you'll see a "Can't connect" page. Start it with Start-Windows.bat / Start-Mac.command and
> click **Try again**.

**Start it automatically when the computer turns on:**
- **Mac:** System Settings → General → **Login Items** → **+** → choose **Start-Mac.command**.
- **Windows:** press **Windows key + R**, type `shell:startup`, press Enter, and put a **shortcut** to
  **Start-Windows.bat** in the folder that opens (right-click Start-Windows.bat → Show more options →
  Create shortcut, then move the shortcut there).

---

## Everyday use

| To… | Do this |
|---|---|
| Start the app | Double-click **Start-Windows.bat** (Mac: **Start-Mac.command**) |
| Stop the app | Close the black window |
| See money still to be received | **Payments** |
| See what went out of stock | **Dashboard** or **Stock summary & stock out** |
| Record a payment received | **Payments** → amount → **Received** |

## Backups: please do this every week

1. Double-click **Backup-Windows.bat** (Mac: **Backup-Mac.command**).
2. A copy of all your data is saved in the **backups** folder inside the app folder.
3. Copy the **backups** folder to a pen drive or Google Drive.

**To restore** a backup: stop the app, then copy `invoicer.sqlite3` and `secret_key` from the backup into
the `instance` folder (replace the files there), and start the app again.

## Getting a newer version later

1. Stop the app and make a backup (above).
2. Extract the new zip to a **new** folder.
3. Copy the **instance** folder from your old app folder into the new folder.
4. Start the app from the new folder. Your data and logins carry over automatically.

## Using it from other locations

Right now the app runs on **this computer only**. People at other locations or on other Wi-Fi networks
can't open it yet. To share it, the app needs to be put on an online server (for example PythonAnywhere
or a cloud server). This is the next step and can be set up when you are ready.

## Troubleshooting

| Problem | Fix |
|---|---|
| Mac: "Apple could not verify Start-Mac.command" | Click **Done**, then **System Settings → Privacy & Security → Open Anyway** (see Step 3). |
| Mac: a box asks to install "command line developer tools" | Python isn't installed yet. Click Cancel and do Step 1 first. |
| "Python is not installed" | Install Python (Step 1) and **tick "Add python.exe to PATH"**. Then restart the computer. |
| "Something went wrong during setup" | Check the internet connection. Delete the `.venv` folder inside the app folder and double-click Start again. |
| Browser says "can't reach this page" | The black window must be open. Wait a few seconds and refresh. |
| The black window shows an error about the address or port being in use | The app is already running in another black window. Use that one, or close it first. |
| Forgot the administrator password | Open the app folder, click the address bar, type `cmd` and press Enter. In the window type `.venv\Scripts\flask --app run create-admin` and follow the questions. |
| Someone is locked out | They typed a wrong password 5 times. Wait 15 minutes, or the admin clicks **Unlock** under **Users & access**. |
