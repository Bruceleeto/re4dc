/* Included immediately after Session ss in platform/card.cpp, under the knob.
 * The worker publishes scalar metadata after accessing its private cached FAT.
 * The UI never follows those buffers and never waits for the worker. */
static Re4dcVmuDialogSnapshot card_dialog_public{};
static maple_device_t* card_dialog_device;
static unsigned card_dialog_cache_valid;
static unsigned card_dialog_epoch, card_dialog_active_epoch;

static void card_dialog_retire_locked()
{
    card_dialog_public = Re4dcVmuDialogSnapshot{};
    card_dialog_device = nullptr;
    card_dialog_cache_valid = 0;
    // Never let a completion from an observed retired session republish itself.
    // Saturation disables presentation publication rather than reusing a token.
    if (card_dialog_epoch != ~0U) ++card_dialog_epoch;
}

static void card_dialog_clear()
{
    const int old = irq_disable();
    card_dialog_retire_locked();
    irq_restore(old);
}

static void card_dialog_begin()
{
    const int old = irq_disable();
    card_dialog_active_epoch = card_dialog_epoch;
    card_dialog_public.flags &= ~RE4DC_VMU_DIALOG_COUNTS;
    card_dialog_public.free_blocks = card_dialog_public.free_files = 0;
    irq_restore(old);
}

static void card_dialog_publish(bool counts)
{
    Re4dcVmuDialogSnapshot next{};
    maple_device_t* dev = nullptr;
    unsigned epoch;
#if !RE4DC_VMU_GCRAW
    /* Same selected-device validity contract as vmus_present. Never repick. */
    const int old = irq_disable();
    epoch = card_dialog_epoch;
    if (epoch == ~0U || card_dialog_active_epoch != epoch) {
        irq_restore(old);
        return;
    }
    const bool cached_counts = card_dialog_cache_valid || (counts && ss.op == kMount);
    if (ss.st.port >= 0 && ss.st.port < 4 && ss.st.unit >= 1 && ss.st.unit <= 2) {
        maple_device_t* live = maple_enum_dev(ss.st.port, ss.st.unit);
        if (live && live == ss.st.dev && live->valid &&
            (live->info.functions & MAPLE_FUNC_MEMCARD)) {
            dev = live;
            next.flags = RE4DC_VMU_DIALOG_SELECTED;
            if (live->info.functions & MAPLE_FUNC_LCD) next.flags |= RE4DC_VMU_DIALOG_LCD;
            next.port = (unsigned) ss.st.port;
            next.slot = (unsigned) ss.st.unit;
        }
    }
    irq_restore(old);
    /* Worker-only cached reads; no display call can access or change the FAT. */
    if (dev && counts && cached_counts && ss.st.mounted == 1) {
        next.free_blocks = vmus_free_blocks(&ss.st);
        next.free_files = vmus_free_dirents(&ss.st);
        next.flags |= RE4DC_VMU_DIALOG_COUNTS;
    }
#else
    (void) counts;
    epoch = card_dialog_epoch;
#endif
    const int saved = irq_disable();
    if (epoch != ~0U && epoch == card_dialog_epoch && card_dialog_active_epoch == epoch) {
        card_dialog_public = next;
        card_dialog_device = dev;
        if (counts && ss.op == kMount && ss.st.mounted == 1) card_dialog_cache_valid = 1;
    }
    irq_restore(saved);
}

static int card_dialog_read(Re4dcVmuDialogSnapshot* out)
{
    if (!out) return 0;
    *out = Re4dcVmuDialogSnapshot{};
#if RE4DC_VMU_GCRAW
    return 0; // Do not relabel the independent GC raw-file compatibility backend.
#else
    const int old = irq_disable();
    *out = card_dialog_public;
    if (out->flags & RE4DC_VMU_DIALOG_SELECTED) {
        maple_device_t* live = maple_enum_dev((int) out->port, (int) out->slot);
        if (!live || live != card_dialog_device || !live->valid ||
            !(live->info.functions & MAPLE_FUNC_MEMCARD)) {
            *out = Re4dcVmuDialogSnapshot{};
            card_dialog_retire_locked();
        }
    }
    /* This is the same rounding used by op_syswrite/vmus_package. It describes
     * one system file, not the virtual GC sector size or game-save estimate. */
    out->system_blocks = (kVms + kR4 + kSysWorkLen + 511U) / 512U;
    if (ss.busy) {
        out->flags &= ~RE4DC_VMU_DIALOG_COUNTS;
        out->free_blocks = out->free_files = 0;
    }
    irq_restore(old);
    return 1;
#endif
}
