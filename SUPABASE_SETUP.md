# Supabase Setup - Step by Step

## Quick Answer: No Manual Creation Needed!

You have a SQL migration file (`supabase_migration.sql`) that creates everything automatically. Just run it in Supabase SQL Editor.

---

## Step-by-Step Instructions

### Step 1: Go to Supabase Dashboard

1. Go to https://supabase.com/dashboard
2. Sign in or create account
3. Create a new project (or select existing)
   - Project name: `inboxv3` (or any name)
   - Database password: (save this!)
   - Region: Choose closest to you
   - Wait 2-3 minutes for project to be ready

### Step 2: Open SQL Editor

1. In your Supabase project dashboard
2. Click **"SQL Editor"** in the left sidebar
3. Click **"New query"** button

### Step 3: Run the Migration

1. Open `supabase_migration.sql` file from this project
2. **Copy ALL the contents** of that file
3. **Paste** into the SQL Editor in Supabase
4. Click **"Run"** button (or press Ctrl+Enter)

**That's it!** The table is created automatically.

### Step 4: Verify Table Was Created

1. In Supabase dashboard, click **"Table Editor"** in left sidebar
2. You should see a table called **`inbox_jobs`**
3. Click on it to see the columns:
   - `id` (UUID)
   - `status` (text)
   - `progress` (integer)
   - `result` (JSONB)
   - etc.

---

## What the Migration Does

The SQL file creates:

1. **Table:** `inbox_jobs`
   - Stores all job records
   - Tracks status, progress, results

2. **Indexes:**
   - Faster queries by status
   - Faster queries by created_at

3. **Constraints:**
   - Ensures status is valid ('pending', 'processing', 'completed', 'failed')

4. **Trigger:**
   - Automatically updates `updated_at` timestamp

---

## Alternative: Manual Creation (Not Recommended)

If you prefer to create manually (not recommended, but possible):

1. Go to **Table Editor**
2. Click **"New table"**
3. Name: `inbox_jobs`
4. Add columns manually (see migration file for schema)
5. Add indexes manually
6. Add constraints manually

**Why not recommended:** The migration file is tested and includes everything (indexes, triggers, constraints). Manual creation is error-prone.

---

## Get Your Credentials

After table is created, get your credentials:

1. Go to **Settings** → **API** (in Supabase dashboard)
2. Copy these two values:

   **Project URL:**
   ```
   https://xxxxx.supabase.co
   ```

   **Service Role Key:**
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
   ⚠️ **Important:** Use **Service Role Key** (not anon key)
   - Service Role Key = Full access (for server-side)
   - Anon Key = Limited access (for client-side)

---

## Add to Environment Variables

Add these to your `.env` file:

```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

And add to Render environment variables (same values).

---

## Troubleshooting

### "Table already exists" Error

If you see this error, the table was already created. That's fine! You can:
- Ignore the error, or
- Drop the table first: `DROP TABLE inbox_jobs;` then run migration again

### "Permission denied" Error

Make sure you're using the **Service Role Key** (not anon key) in your environment variables.

### Can't find SQL Editor

- Make sure you're in the Supabase dashboard (not docs)
- Look in left sidebar for "SQL Editor"
- If you don't see it, you might need to wait for project to finish initializing

---

## Summary

✅ **No manual table creation needed**  
✅ **Just run the SQL migration file**  
✅ **Takes 30 seconds**  
✅ **Everything is automated**

The migration file (`supabase_migration.sql`) does all the work for you!

