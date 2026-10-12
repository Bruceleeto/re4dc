/* Public fallback (port/dreamcast/game/public-assets) for the private vmu_dialog_english.inc.
 * The private file pairs the exact English memory card messages of the GameCube release with
 * VMU wording. This table is empty (one entry whose id matches no message), so the card screens
 * show the game's own GameCube text ("Memory Card in Slot A") instead of the VMU wording. */
static const CardVmuText card_vmu_text[] = {
    {0xFFFFFFFFu, 0, 0, "", ""},
};
