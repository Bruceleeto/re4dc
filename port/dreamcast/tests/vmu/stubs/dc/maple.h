#pragma once
#include <stdint.h>
#define MAPLE_FUNC_CONTROLLER 1u
#define MAPLE_FUNC_LCD 2u
#define MAPLE_EOK 0
struct maple_device_t {
    int port, unit;
    struct { unsigned functions, connector_direction; } info;
};
maple_device_t* maple_enum_type(int index,unsigned function);
maple_device_t* maple_enum_dev(int port,int unit);
