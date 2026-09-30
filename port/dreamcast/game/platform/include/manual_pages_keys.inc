// native_ui.cpp only; inside its existing private namespace, before image_key.
// Route packages + the frozen camera package. The table order is the public enum.
struct ManualPageEntry { Re4dcManualPageContext context; Key keys[2]; };
static const ManualPageEntry manual_pages[RE4DC_MANUAL_PAGE_COUNT]={
    {{1,1,2,0,"SS/Eng/f01r.tpl"},{{0x5613a245U,0xe1e18d42U},{0x92c20923U,0xd7980c6cU}}},
    {{1,2,3,0,"SS/Eng/f01s.tpl"},{{0x7e5c423dU,0xbc4dd908U},{0x80583d0dU,0x207c46eaU}}},
    {{1,3,4,0,"SS/Eng/f01t.tpl"},{{0xa3ffa308U,0xda3d1281U},{0xae79e0c3U,0x769d1f29U}}},
    {{1,4,5,0,"SS/Eng/f01q.tpl"},{{0xb4e65edbU,0x3cb9a1b0U},{0x1932f698U,0x5964cb37U}}},
    {{3,1,2,12,"SS/Eng/f03q.tpl"},{{0x011dcfbeU,0x8fd34d9cU},{0x9ee068c9U,0xeb022a67U}}},
    {{3,2,3,12,"SS/Eng/f03r.tpl"},{{0x576f01b9U,0x10178fc9U},{0x47e592e1U,0xaa6fa39eU}}},
    {{3,3,4,12,"SS/Eng/f03s.tpl"},{{0x5621bcacU,0x319ac6e5U},{0x45ea8b33U,0xe5d1e362U}}},
    {{1,0,1,0,nullptr},{{0x599b2dbbU,0x580b72bcU},{0,0}}}, // original f01a cover only
};
static Re4dcUiImage manual_page_image(unsigned row,unsigned variant){
    return {&manual_pages[row].keys[variant],nullptr,640,360,14,0xffffffffU,0};
}
static Key manual_generic_key;   // the adopted generic file picture (re4dc_ui_manual_generic_identify)
static int manual_page_key(const Re4dcUiImage& image,Key& key){
    if(image.pixels==&manual_generic_key){
        if(!same_image(image,{&manual_generic_key,nullptr,640,360,14,0xffffffffU,0}))return -1;
        key=manual_generic_key;return 1;
    }
    for(unsigned row=0;row<RE4DC_MANUAL_PAGE_COUNT;++row)
        for(unsigned variant=0;variant<(manual_pages[row].context.companion_path ? 2U : 1U);++variant)
            if(image.pixels==&manual_pages[row].keys[variant]){
                if(!same_image(image,manual_page_image(row,variant)))return -1;
                key=manual_pages[row].keys[variant];return 1;
            }
    return 0;
}
