# Getting started: Shanumkha Invoices & Stock

The app is installed on **every computer** that uses it. All computers share **one online database (Neon)**,
so a change made by anyone shows up for everyone, and each person only sees and changes what their login allows.
Setting up a computer takes about 15 minutes; you don't need to type commands.

---

## Step 0: Create the shared database (administrator, once only)

Neon is a company that keeps your database online, safely, with automatic backups. It is **not a website**:
nobody can see it, and nothing appears in Google. Only computers that have the connection string can reach it.

1. Go to **https://neon.tech** → **Sign up** (you can use your Google account).
2. Create a **project**: name it `shanumkha`. For **Region** choose the one closest to you, e.g.
   **AWS Asia Pacific (Singapore)**. Click **Create project**.
3. On the project dashboard click **Connect**. Keep **Connection pooling** switched on, then click
   **Copy snippet** or the copy button next to the connection string. It looks like
   `postgresql://neondb_owner:xxxx@ep-xxxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
4. Keep this connection string **private**, like a bank password. You'll paste it once on each computer
   (Step 3). Send it to your team personally (e.g. WhatsApp to the person, not a group), never by public email.

> The free Neon plan is enough to start with. After a few minutes of no use, Neon pauses the database; the
> first click after that can take a second or two, then everything is fast again.


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
- It then asks **"Where should this computer keep the app's data?"**: type **1** (shared online database)
  and press Enter, then **paste the connection string** (Windows: right-click; Mac: ⌘ Cmd + V) and press Enter.
  **Nothing appears while you paste. That's on purpose, to keep the password private.** The window then shows
  the string with the password as `****` and asks you to confirm the database name (it must be **your**
  database, e.g. `shanmukaconsumersinvoice`, not `neondb`). It checks the connection and saves it. You won't be
  asked again on this computer.
- **Never share a photo or screenshot of the connection string.** If that happens, reset the password in Neon
  (Roles → neondb_owner → Reset password) and connect again with the new string.
- Your browser then opens the app at **http://127.0.0.1:8765**.

**Mac:** double-click **Start-Mac.command**. The first time, macOS says *"Apple could not verify
'Start-Mac.command'…"*. Click **Done** (not "Move to Bin"), then either:

- open ** → System Settings → Privacy & Security**, scroll down, click **Open Anyway**, enter your Mac
  password and click **Open Anyway** again, **or**
- open **Terminal** (⌘ Space, type Terminal) and paste this line, then press Enter. It unblocks both Mac files at once:
  `xattr -dr com.apple.quarantine ~/Documents/Shanumkha-Invoices && bash ~/Documents/Shanumkha-Invoices/Start-Mac.command`

This warning appears for any app not from the App Store; it only has to be allowed once.

> **Keep the black window open while you use the app.** Closing it stops the app.
> To start again tomorrow, double-click **Start-Windows.bat** again (it will be fast after the first time).
> If the browser didn't open, open it yourself and go to **http://127.0.0.1:8765**.

## Step 4: Create the administrator login (first computer only)

On the **very first computer** connected to the new database, the first page asks you to **create the
administrator**. Enter your name, a username and a password (at least 8 characters). **Write it down somewhere safe.**

On every other computer you'll see the **Log in** page instead: log in with the username and password the
administrator gave you.

> Already used the app on this computer before Neon? When you paste the connection string, the app offers to
> **copy this computer's data into the shared database** (only if the shared database is still empty). Type **y**.

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

- **Google Chrome or Microsoft Edge (Windows or Mac):** open **http://127.0.0.1:8765**, then click the
  **install icon** at the right end of the address bar (a small screen with a down arrow) → **Install**.
  Or use the **⋮** menu → **Cast, save and share** → **Install page as app** (Edge: **⋯** → **Apps** →
  **Install this site as an app**).
- **Safari on Mac:** open **http://127.0.0.1:8765**, then **File → Add to Dock** → **Add**.

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

Neon keeps its own copies of your database. As extra safety, keep your own copy too:

1. On any one computer, double-click **Backup-Windows.bat** (Mac: **Backup-Mac.command**).
2. A full copy of the shared data is downloaded into the **backups** folder inside the app folder.
3. Copy the **backups** folder to a pen drive or Google Drive.

If you ever need to restore from one of these copies, keep the backup file and ask for help: it can be loaded
back into a new Neon database.

## Getting a newer version later

1. Stop the app and make a backup (above).
2. Extract the new zip to a **new** folder.
3. Copy the **instance** folder from your old app folder into the new folder.
4. Start the app from the new folder. Your data and logins carry over automatically.

## Adding another computer (any location, any Wi-Fi)

1. On the new computer do **Step 1** (Python), **Step 2** (unzip) and **Step 3** (start, type **1**, paste the
   connection string).
2. The person logs in with the username and password the administrator created for them under **Users & access**.

That's all: every computer sees the same invoices, stock, payments and so on, live.

**Someone leaves or a laptop is lost?** The administrator deactivates their login under **Users & access**.
If the laptop itself might be misused, also reset the database password in Neon (**Roles → Reset password**)
and paste the new connection string on the other computers (see Troubleshooting: *Change the database*).

> **Important:** every computer that is connected stores the connection string (in `instance\database_url.txt`).
> Someone with technical skills and access to that computer's files could use it to open the database directly,
> outside the app and its access rules. Only install the app on computers of people you trust.

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
| "Could not connect" / "password authentication failed" when pasting | Copy the connection string again from Neon (**Connect**), including the password, and paste the whole line. |
| The app is slow on the first click of the day | Neon was paused to save resources; it wakes up in a second or two. |
| Change the database (or switch to "this computer only") | Delete the file `instance/database_url.txt` in the app folder and start the app again; it asks again. |
| Chrome shows "Access to 127.0.0.1 was denied – HTTP ERROR 403" | You are on an old address. Open **http://127.0.0.1:8765** (port 5000 belongs to the Mac's AirPlay Receiver). |
| Someone is locked out | They typed a wrong password 5 times. Wait 15 minutes, or the admin clicks **Unlock** under **Users & access**. |
