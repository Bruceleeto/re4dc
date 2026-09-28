// Included inside native_ui's anonymous namespace, after same_image.
// R4HM v1: constant source RGB206 + exact source mask alpha, native4444.
// These addresses identify immutable prepared packages; they are not pixels.
static const Key hud_mask_keys[2]={{0x84d450d5U,0xede2f8a1U},{0xacfcae72U,0xccf1609cU}};
static Re4dcUiImage hud_mask_image(unsigned index) {
    return {hud_mask_keys+index,nullptr,64,64,6,0xffffffffU,0};
}
static int hud_mask_image_key(const Re4dcUiImage& image,Key& key) {
    for(unsigned i=0;i<2;++i)if(image.pixels==hud_mask_keys+i) {
        if(!same_image(image,hud_mask_image(i)))return -1;
        key=hud_mask_keys[i];return 1;
    }
    return 0;
}
