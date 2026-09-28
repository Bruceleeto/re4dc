    // Included in FrameLedger's public section. Explicit, sticky choice after
    // original source preparation. 0 undecided, 1 source, 2 owned native.
    bool presentation_address(const FrameIdentity& now,std::uintptr_t address)const {
        if(!valid(now) || phase_!=Ready)return false;
        for(std::uint32_t k=0;k<count_;++k)if(entries_[k].model.address==address)return true;
        return false;
    }
    bool presentation_choice(const FrameIdentity& now,const ModelIdentity& model,unsigned& choice)const {
        if(!valid(now) || phase_!=Ready)return false;
        for(std::uint32_t k=0;k<count_;++k)if(entries_[k].model==model) {
            const auto& e=entries_[k];
            if(e.path!=ModelPath::Source || !e.prepared)return false;
            choice=e.presentation;return true;
        }
        return false;
    }
    bool presentation_choose(const FrameIdentity& now,const ModelIdentity& model,unsigned choice) {
        if(!valid(now) || phase_!=Ready)return false;
        for(std::uint32_t k=0;k<count_;++k)if(entries_[k].model==model) {
            auto& e=entries_[k];
            if(e.path!=ModelPath::Source || !e.prepared ||
               !((e.presentation==0 && choice==1) || (e.presentation==1 && choice==2)))return false;
            e.presentation=choice;return true;
        }
        return false;
    }
