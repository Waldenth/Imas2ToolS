import os
import subprocess

import os


def convert_png_to_dds_task(progress, files, dds_format, nvdxt_path):

    total = len(files)

    for i, file in enumerate(files, 1):

        name = os.path.basename(file)

        progress(f"Converting DDS {i}/{total}: {name}")

        convert_png_to_dds(file, dds_format, nvdxt_path)
    
    return total


def convert_png_to_dds(png_path, dds_format, nvdxt_path):

    # 示例逻辑
    output_dir = os.path.dirname(png_path) + "/output_dds"
    os.makedirs(output_dir, exist_ok=True)
    
    dds_path = os.path.join(output_dir, os.path.splitext(os.path.basename(png_path))[0] + ".dds")
    # 实际转换逻辑
    # 使用 nvdxt.exe 进行转换，确保 nvdxt.exe 在系统路径中或者提供了正确的路径
    try:
        cmd = [
            nvdxt_path,
            "-file", png_path,
            "-outdir", output_dir,
            "-rel_scale", "1.0", "1.0",
            "-nomipmap",
            f"-{dds_format.lower()}"
        ]
        subprocess.run(
            cmd, 
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to convert {png_path} to DDS\n"
            f"cmd: {e.cmd}\n"
            f"returncode: {e.returncode}\n"
            f"output:\n{e.stdout}"
        )
        #raise RuntimeError(f"Failed to convert {png_path} to DDS: {e}")

    return dds_path