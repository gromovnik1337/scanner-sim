from utils import *


def configure_camera_geometry(config, cam_geom):
    if type(cam_geom) is str:
        cam_geom = load_calibration(cam_geom)
    assert type(cam_geom) is dict

    w, h = cam_geom["image_width, pixels"], cam_geom["image_height, pixels"]
    config["cam_width"], config["cam_height"] = w, h
    config["cam_fov_y"] = 2 * np.arctan((h / 2.) / cam_geom["new_mtx"][1, 1]) * 180. / np.pi
    config["cam_pixelAspect"] = cam_geom["new_mtx"][0, 0] / cam_geom["new_mtx"][1, 1]
    # config["cam_pixelAspect"] = 2  # Override for debugging

    # TODO: make use of cam_geom["new_mtx"][:2, 2] and cropping feature in mitsuba to simulate optical axis offset


def configure_camera_focus(config, cam_focus, tolerances_factor=1.07, wavelength_nm=550):
    if type(cam_focus) is str:
        cam_focus = load_calibration(cam_focus)
    assert type(cam_focus) is dict

    # Convert values to mitsuba scene units (meters)
    config["cam_focus"] = cam_focus["focus, mm"] / 1000.
    # Convert aperture diameter (focus_calib convention) to aperture radius (mitsuba convention)
    config["cam_aperture"] = cam_focus["aperture, mm"] / 2. / 1000.
    # Diffraction limit (in radians) depends on camera aperture (in meters)
    config["cam_diffLimit"] = 1.22 * wavelength_nm * 1.e-9 / (2. * config["cam_aperture"])
    # Account for manufacturing tolerances of the lens and convert from radians to degrees
    config["cam_diffLimit"] *= tolerances_factor * (180. / np.pi)
    # config["diffLimit"] = 2.65  # Temporary override (in-pixels value)


def configure_projector_geometry(config, proj_geom, brightness=10, gap_size=0):
    if type(proj_geom) is str:
        proj_geom = load_calibration(proj_geom)
    assert type(proj_geom) is dict

    w, h = proj_geom["image_width, pixels"], proj_geom["image_height, pixels"]
    config["proj_width"], config["proj_height"] = w, h
    mtx = proj_geom["new_mtx"]
    config["proj_scaleX"], config["proj_scaleY"] = mtx[0, 0], mtx[1, 1]
    config["proj_offsetX"], config["proj_offsetY"] = mtx[0, 2], mtx[1, 2]
    # config["proj_beamwidth"], config["proj_cutoff"] = 2.0, 3.0

    # Projector brigtness
    config["proj_intensity"] = brightness
    # Simulate gaps between micro-mirrors in DMD projectors
    config["proj_gapSize"] = gap_size


def configure_projector_focus(config, proj_focus, diffLimit=0):
    if type(proj_focus) is str:
        proj_focus = load_calibration(proj_focus)
    assert type(proj_focus) is dict

    # Convert values to mitsuba scene units (meters)
    config["proj_focus"] = proj_focus["focus, mm"] / 1000.
    # Convert aperture diameter (focus_calib convention) to aperture radius (mitsuba convention)
    config["proj_aperture"] = proj_focus["aperture, mm"] / 2. / 1000.
    # Diffraction limit on projector resolution
    config["proj_diffLimit"] = diffLimit


def configure_object_geometry(config, stage_geom):
    pass


def process_images(config, cam_geom, cam_vignetting, wb):
    pass


def process_patterns(config, proj_geom, proj_response, proj_vignetting):
    pass


def load_template(filename):
    with open(filename, "r") as f:
        lines = f.readlines()

    header, body = [], []
    for i, line in enumerate(lines):
        if not line.startswith("<scene"):
            header.append(line)
        else:
            header.append(line)
            body = lines[i+1:]
            break

    return header, body


def generate_scene(header, body, config, filename):
    with open(filename, "w") as f:
        f.writelines(header)

        for key, value in config.items():
            f.write("\t<default name=\"%s\" value=\"%s\"/>\n" % (key, str(value)))

        f.write("\n")
        f.writelines(body)


def source(script, update=True):
    pipe = subprocess.Popen("source %s; env" % script, stdout=subprocess.PIPE,
                            shell=True, executable="/bin/bash")
    data = pipe.communicate()[0].decode("utf-8")

    env = dict([line.split("=", 1) for line in data.splitlines()])

    if update:
        print("Updating environment:", env)
        os.environ.update(env)

    return env


def render_scenes(filenames_template, output_folder=None, verbose=True):
    scenes = glob.glob(filenames_template)
    if output_folder is not None:
        output = ["-o", output_folder]
    else:
        output = []

    for i, scene in enumerate(sorted(scenes)):
        print("\nScene %d of %d:" % (i+1, len(scenes)), scene)

        proc = subprocess.Popen(["mitsuba", *output, scene], stdout=subprocess.PIPE, universal_newlines=True)

        for line in proc.stdout:
            if verbose:
                print(line[:-1])


if __name__ == "__main__":
    source("/home/yurii/software/mitsuba/setpath.sh")

    proc = subprocess.Popen(["mitsuba", "-h"], stdout=subprocess.PIPE, universal_newlines=True)
    for line in proc.stdout:
        print(line[:-1])
