#pragma once
// Host shim for ps2_world_check.cpp: room_package.hpp names KOS file handles in a member it never uses here.
typedef int file_t;
#define FILEHND_INVALID (-1)
