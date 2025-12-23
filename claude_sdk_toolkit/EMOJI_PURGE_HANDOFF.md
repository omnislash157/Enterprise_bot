# Frontend Emoji Purge - Claude Code Handoff

## Priority: P1 - UI Polish
## Risk Level: LOW (cosmetic changes only)

---

## QUICK EXECUTION SUMMARY

Files to fix (in order):
1. `frontend/src/lib/components/ChatOverlay.svelte` - 4 fixes (lines 259, 275, 285, 307)
2. `frontend/src/lib/components/DepartmentSelector.svelte` - 1 fix (line 72)
3. `frontend/src/lib/components/CreditForm.svelte` - 7 fixes (lines 275, 335, 415, 443, 450, 584, 602)
4. `frontend/src/lib/components/DupeOverrideModal.svelte` - 2 fixes (lines 85, 102)
5. `frontend/src/lib/components/admin/UserRow.svelte` - 2 fixes (line 182)

**Total: 16 emoji replacements across 5 files**

After fixes:
```bash
cd frontend
npm run build
npm run preview  # verify visually
```

---

## SPECIFIC FIXES NEEDED (Copy-Paste Ready)

### ChatOverlay.svelte

**Line 259 - Logo Icon:**
```svelte
<!-- BEFORE -->
<span class="logo-icon">Ã¢â€"Ë†</span>

<!-- AFTER -->
<svg class="logo-icon" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
  <path d="M12 2L2 12l10 10 10-10L12 2zm0 3l7 7-7 7-7-7 7-7z"/>
</svg>
```

**Line 275 - Logout Icon:**
```svelte
<!-- BEFORE -->
<span class="logout-icon">Ã¢ÂÂ»</span>

<!-- AFTER -->
<svg class="logout-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
</svg>
```

**Line 285 - Empty State Icon:**
```svelte
<!-- BEFORE -->
<div class="empty-icon">Ã¢â€"â€¡</div>

<!-- AFTER -->
<div class="empty-icon">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
  </svg>
</div>
```

**Line 307 - Typing Cursor:**
```svelte
<!-- BEFORE -->
<span class="typing-cursor">Ã¢â€"Å </span>

<!-- AFTER (just use CSS, empty span) -->
<span class="typing-cursor"></span>
```

Then update the `.typing-cursor` CSS (around line 640):
```css
.message.streaming .typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: #00ff41;
  animation: blink 0.8s step-end infinite;
  margin-left: 2px;
  vertical-align: text-bottom;
}
```

### DepartmentSelector.svelte

**Line 72 - Dropdown Arrow:**
```svelte
<!-- BEFORE -->
<span class="dropdown-arrow">Ã¢â€"Â¼</span>

<!-- AFTER -->
<span class="dropdown-arrow">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="12" height="12">
    <path d="M6 9l6 6 6-6"/>
  </svg>
</span>
```

### CreditForm.svelte

**Lines 275, 335 - Accordion Trigger Icons:**
```svelte
<!-- BEFORE -->
<span class="trigger-icon">Ã¢â€"Â¾</span>

<!-- AFTER -->
<svg class="trigger-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
  <path d="M6 9l6 6 6-6"/>
</svg>
```

**Line 415 - Checkmark:**
```svelte
<!-- BEFORE -->
<span class="check-mark">Ã¢Å"â€œ</span>

<!-- AFTER -->
<svg class="check-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14">
  <path d="M20 6L9 17l-5-5"/>
</svg>
```

**Lines 443, 584, 602 - Warning Icons:**
```svelte
<!-- BEFORE -->
<span class="notice-icon">Ã¢Å¡ </span>
<span class="error-tag">Ã¢Å¡  {error}</span>
<span>Ã¢Å¡  {$credit.error}</span>

<!-- AFTER -->
<span class="notice-icon">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
    <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
  </svg>
</span>
<span class="error-tag">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12" style="display:inline;vertical-align:middle;margin-right:4px;">
    <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
  </svg>
  {error}
</span>
```

**Line 450 - Info Icon:**
```svelte
<!-- BEFORE -->
<span class="notice-icon">Ã¢â€ â€œ</span>

<!-- AFTER -->
<span class="notice-icon">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
    <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
  </svg>
</span>
```

### DupeOverrideModal.svelte

**Line 85 - Header Warning Icon:**
```svelte
<!-- BEFORE -->
<div class="header-icon">Ã¢Å¡ </div>

<!-- AFTER -->
<div class="header-icon">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32">
    <path d="M12 9v4M12 17h.01"/>
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
  </svg>
</div>
```

**Line 102 - Status Icons:**
```svelte
<!-- BEFORE -->
{item.status === 'blocked' ? 'Ã°Å¸â€ºâ€˜' : 'Ã¢Å¡ '}

<!-- AFTER (use CSS classes instead) -->
<span class="status-icon" class:blocked={item.status === 'blocked'}>
  {#if item.status === 'blocked'}
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
      <circle cx="12" cy="12" r="10"/><path d="M4.93 4.93l14.14 14.14"/>
    </svg>
  {:else}
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
      <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
    </svg>
  {/if}
</span>
```

### UserRow.svelte

**Line 182 - Expand/Collapse Arrows:**
```svelte
<!-- BEFORE -->
{expanded ? 'Ã¢â€"Â¼' : 'Ã¢â€"Â¶'}

<!-- AFTER -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" 
     style="transform: rotate({expanded ? 0 : -90}deg); transition: transform 0.2s;">
  <path d="M6 9l6 6 6-6"/>
</svg>
```

---

## The Problem

UTF-8 emoji/unicode characters are rendering as mojibake in production:
- `â—^` instead of logo icon
- `â-¼` instead of dropdown chevron  
- `â—‡` instead of empty state icon
- `âD»` instead of logout icon
- `â–Å` instead of cursor

This happens because emoji codepoints get mangled through build/deploy pipeline or font rendering.

---

## The Rule

**NO EMOJI OR UNICODE SYMBOLS IN PRODUCTION CODE. EVER.**

Replace with:
1. **SVG inline** (preferred) - scales perfectly, no encoding issues
2. **CSS pseudo-elements** - for simple shapes
3. **Plain text** - when appropriate

---

## Files to Scan

### High Priority (visible in screenshot)
```
frontend/src/lib/components/ChatOverlay.svelte      # Header icon, empty state, cursor
frontend/src/lib/components/DepartmentSelector.svelte  # Dropdown chevron
frontend/src/lib/components/ribbon/UserMenu.svelte     # Logout icon
frontend/src/lib/components/ribbon/IntelligenceRibbon.svelte  # Any nav icons
```

### Medium Priority (likely have emoji)
```
frontend/src/lib/components/Login.svelte
frontend/src/lib/components/CheekyLoader.svelte
frontend/src/lib/components/CheekyInline.svelte
frontend/src/lib/components/CheekyToast.svelte
frontend/src/lib/components/ToastProvider.svelte
frontend/src/lib/components/CreditForm.svelte
frontend/src/lib/components/admin/*.svelte
```

### Low Priority (check anyway)
```
frontend/src/routes/**/*.svelte
frontend/src/lib/stores/cheeky.ts    # Status phrases might have emoji
```

---

## Search Patterns

Run these to find all emoji/unicode:

```bash
# Find common unicode symbols (arrows, shapes, etc.)
grep -rn '[▲▼◆◇●○►◄★☆✓✗→←↑↓⬆⬇➜➤▶◀■□▪▫•‣⁃※†‡§¶©®™°±×÷≠≈≤≥∞∑∏√∫]' frontend/src/

# Find emoji ranges (will catch most emoji)
grep -rPn '[\x{1F300}-\x{1F9FF}]' frontend/src/

# Find any non-ASCII (broader search)
grep -rPn '[^\x00-\x7F]' frontend/src/ --include="*.svelte" --include="*.ts"

# Specific patterns seen in screenshot
grep -rn 'â' frontend/src/
grep -rn '◆\|◇\|▼\|▲\|►\|◄\|●\|○' frontend/src/
```

---

## Replacement Guide

### Logo/Brand Icon
**Before:** `<span class="logo-icon">◆</span>` or similar
**After:**
```svelte
<svg class="logo-icon" viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
  <path d="M12 2L2 12l10 10 10-10L12 2zm0 3.5L18.5 12 12 18.5 5.5 12 12 5.5z"/>
</svg>
```

### Dropdown Chevron
**Before:** `▼` or `▾` or `⌄`
**After:**
```svelte
<svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
  <path d="M6 9l6 6 6-6"/>
</svg>
```

### Logout/Exit Icon
**Before:** `⏻` or `↪` or similar
**After:**
```svelte
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
</svg>
```

### Empty State Icon
**Before:** `◇` or `⬡` or similar
**After:**
```svelte
<svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
</svg>
```

### Typing Cursor
**Before:** `▌` or `█` or `|`
**After:** Use CSS animation
```svelte
<span class="typing-cursor"></span>

<style>
  .typing-cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: #00ff41;
    animation: blink 0.8s step-end infinite;
    margin-left: 2px;
    vertical-align: text-bottom;
  }
  
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
</style>
```

### Status Dot (Online indicator)
**Before:** `●` or `•`
**After:** CSS
```svelte
<span class="status-dot"></span>

<style>
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #00ff41;
    display: inline-block;
  }
</style>
```

### Checkmarks and X marks
**Before:** `✓` `✗` `✔` `✘`
**After:**
```svelte
<!-- Checkmark -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="16" height="16">
  <path d="M20 6L9 17l-5-5"/>
</svg>

<!-- X mark -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="16" height="16">
  <path d="M18 6L6 18M6 6l12 12"/>
</svg>
```

### Arrows
**Before:** `→` `←` `↑` `↓` `➜` `►`
**After:**
```svelte
<!-- Right arrow (send button) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
</svg>

<!-- Simple arrow -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M5 12h14M12 5l7 7-7 7"/>
</svg>
```

---

## Execution Steps

### Step 1: Audit
```bash
cd frontend

# Create audit file
echo "=== EMOJI AUDIT ===" > /tmp/emoji-audit.txt
grep -rn '[^\x00-\x7F]' src/ --include="*.svelte" --include="*.ts" >> /tmp/emoji-audit.txt 2>&1

cat /tmp/emoji-audit.txt
```

### Step 2: Fix Each File
For each file with emoji:
1. Open the file
2. Identify each emoji/unicode character
3. Replace with appropriate SVG or CSS
4. Verify the replacement renders correctly

### Step 3: Verify Build
```bash
npm run build
npm run preview
# Check all pages visually
```

### Step 4: Test Checklist
- [ ] Chat page header icon renders
- [ ] Department dropdown chevron renders
- [ ] Logout button icon renders
- [ ] Empty state icon renders
- [ ] Typing cursor animates
- [ ] Online status dot shows
- [ ] All toast notifications render
- [ ] Credit form icons render
- [ ] Admin dashboard icons render

---

## Common SVG Icon Set

If you need more icons, here's a consistent set using the same style:

```svelte
<!-- User -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="7" r="4"/>
  <path d="M5.5 21a7.5 7.5 0 0115 0"/>
</svg>

<!-- Settings/Gear -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
</svg>

<!-- Search -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="11" cy="11" r="8"/>
  <path d="M21 21l-4.35-4.35"/>
</svg>

<!-- Menu (hamburger) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M3 12h18M3 6h18M3 18h18"/>
</svg>

<!-- Close/X -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M18 6L6 18M6 6l12 12"/>
</svg>

<!-- Plus -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M12 5v14M5 12h14"/>
</svg>

<!-- Warning/Alert -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M12 9v4M12 17h.01"/>
  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
</svg>

<!-- Info -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="10"/>
  <path d="M12 16v-4M12 8h.01"/>
</svg>

<!-- Brain/Intelligence (for logo) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
  <path d="M12 2a7 7 0 00-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 002 2h4a2 2 0 002-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 00-7-7z"/>
  <path d="M9 21h6M12 17v4"/>
</svg>
```

---

## Safety Notes

1. **Test locally first** - `npm run dev` and check each page
2. **One file at a time** - Don't batch replace without verification
3. **Keep the same class names** - Only change the content, not the CSS hooks
4. **Preserve accessibility** - Add `aria-label` to icon-only buttons
5. **Match the theme** - Use `currentColor` for SVG stroke/fill to inherit text color

---

## Git Commit

After all changes:
```bash
git add -A
git commit -m "fix: replace all emoji/unicode with SVG icons

- Fixes UTF-8 mojibake rendering issues in production
- Replaced unicode symbols with inline SVGs
- No functional changes, cosmetic only
- Tested all pages for correct icon rendering"
git push origin main
```

---

## Verification Screenshots Needed

After fix, capture:
1. Chat page with header, dropdown, and empty state
2. Chat page with active conversation (typing cursor)
3. Admin dropdown menu
4. Any toast notifications
5. Credit form (if it has icons)

---

## Final Verification Command

Run this to confirm no mojibake remains:
```bash
# Should return NOTHING if fix is complete
grep -rn 'Ã¢' frontend/src/ --include="*.svelte" --include="*.ts"

# Double-check for common unicode patterns
grep -rn '▼\|▲\|◆\|◇\|●\|✓\|✗\|⚠\|ℹ' frontend/src/ --include="*.svelte"
```

If either grep returns results, there are still emoji to fix.
