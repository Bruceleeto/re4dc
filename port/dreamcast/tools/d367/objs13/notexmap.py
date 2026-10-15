# negative test for tex_size_check ORDER: run ps2_objects_tex.py with ps2_objects.TEX_MAPS cleared
import sys, runpy
sys.path.insert(0, sys.argv.pop(1))
import ps2_objects
ps2_objects.TEX_MAPS.clear()
sys.argv[0] = 'ps2_objects_tex.py'
runpy.run_path('ps2_objects_tex.py', run_name='__main__')
