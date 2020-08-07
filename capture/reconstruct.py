import os
import cv2
import time
import json
import queue
import pickle
import meshio
import open3d as o3d
import numpy as np
import matplotlib.pyplot as plt
import scipy.ndimage.morphology as morph
from scipy.ndimage.filters import gaussian_filter
from sklearn.decomposition import PCA

from hdr import *
from projector import *
from scan import *
from display import *


def gray_to_bin(num):
    num = np.bitwise_xor(num, np.right_shift(num, 16))
    num = np.bitwise_xor(num, np.right_shift(num, 8))
    num = np.bitwise_xor(num, np.right_shift(num, 4))
    num = np.bitwise_xor(num, np.right_shift(num, 2))
    num = np.bitwise_xor(num, np.right_shift(num, 1))
    return num


def load_cached(path):
    if not os.path.isfile(path + "dark.npy"):
        dark = load_openexr(path + "0.exr")
        np.save(path + "dark", np.array(dark))

    if not os.path.isfile(path + "white.npy"):
        white = load_openexr(path + "1.exr")
        np.save(path + "white", np.array(white))

    if not os.path.isfile(path + "hor.npy") or not os.path.isfile(path + "hor_i.npy"):
        hor, hor_i = [], []
        for i in range(11):
            hor.append(load_openexr(path + "%d.exr" % (100 + i)))
            hor_i.append(load_openexr(path + "%d.exr" % (200 + i)))

        np.save(path + "hor", np.array(hor))
        np.save(path + "hor_i", np.array(hor_i))

    if not os.path.isfile(path + "ver.npy") or not os.path.isfile(path + "ver_i.npy"):
        ver, ver_i = [], []
        for i in range(11):
            ver.append(load_openexr(path + "%d.exr" % (300 + i)))
            ver_i.append(load_openexr(path + "%d.exr" % (400 + i)))

        np.save(path + "ver", np.array(ver))
        np.save(path + "ver_i", np.array(ver_i))

    return np.load(path + "dark.npy"), np.load(path + "white.npy"), \
           np.load(path + "hor.npy"), np.load(path + "hor_i.npy"), \
           np.load(path + "ver.npy"), np.load(path + "ver_i.npy")


def decode_cached(path, hdrs=None, plot=True):
    if not os.path.isfile(path + "ver.npy") or not os.path.isfile(path + "ver_i.npy") or hdrs is not None:
        dark, white, hor, hor_i, ver, ver_i = hdrs

        white -= dark
        hor -= dark
        hor_i -= dark
        ver -= dark
        ver_i -= dark

        save_openexr(path + "subtracted%d.exr" % 0, hor[0, ...])

        w_mask = white > 0.07*np.max(white)
        struct = scipy.ndimage.generate_binary_structure(2, 1)
        w_mask = morph.binary_erosion(w_mask, struct, 2)

        diff = np.abs(hor[0, ...] - hor_i[0, ...])
        diff = gaussian_filter(diff, sigma=3)
        d_mask = diff > 0.07*np.max(diff)
        d_mask = morph.binary_erosion(d_mask, struct, 2)

        mask = w_mask & d_mask
        mask = morph.binary_erosion(mask, struct, 2)

        idx = np.nonzero(mask)

        hor_m = hor > hor_i
        ver_m = ver > ver_i
        hor2 = np.zeros_like(hor_m)
        ver2 = np.zeros_like(ver_m)
        hor2[:, idx[0], idx[1]] = hor_m[:, idx[0], idx[1]]
        ver2[:, idx[0], idx[1]] = ver_m[:, idx[0], idx[1]]

        h = np.zeros_like(w_mask, dtype=np.int)
        v = np.zeros_like(w_mask, dtype=np.int)

        for i in range(11):
            h = np.bitwise_or(h, np.left_shift(hor2[i, ...].astype(np.int), i))
            v = np.bitwise_or(v, np.left_shift(ver2[i, ...].astype(np.int), i))

        h = gray_to_bin(h)
        v = gray_to_bin(v)
        r, c = np.nonzero((h > 0) & (v > 0))
        p_r, p_c = h[r, c].ravel(), v[r, c].ravel()
        cam = np.stack([c, r], axis=1)
        proj = np.stack([p_c, p_r], axis=1)

        np.save(path + "cam", cam)
        np.save(path + "proj", proj)

        if plot:
            plt.figure("masks")
            plt.subplot(2, 2, 1)
            plt.title("white")
            plt.imshow(white)
            plt.subplot(2, 2, 2)
            plt.title("diff")
            plt.imshow(diff)
            plt.subplot(2, 2, 3)
            plt.title("w_mask")
            plt.imshow(w_mask)
            plt.subplot(2, 2, 4)
            plt.title("d_mask")
            plt.imshow(d_mask)
            plt.tight_layout()

            plt.figure("mask")
            plt.imshow(mask)

    return np.load(path + "cam.npy"), np.load(path + "proj.npy")


def triangulate(p_cam, p_proj, cam_calib, proj_calib):
    ret, cam_mtx, cam_dist, rvecs, tvecs = cam_calib
    origin, R, proj_mtx, proj_dist = proj_calib

    cam2 = cv2.undistortPoints(p_cam.reshape(-1, 2).astype(np.float), cam_mtx, cam_dist).reshape((-1, 2))
    proj2 = cv2.undistortPoints(p_proj.reshape(-1, 2).astype(np.float), proj_mtx, proj_dist).reshape((-1, 2))

    cam_3d = np.concatenate([cam2, np.ones((cam2.shape[0], 1))], axis=1)
    proj_3d = np.concatenate([proj2, np.ones((proj2.shape[0], 1))], axis=1)

    proj_3d = np.matmul(R, proj_3d.T).T

    v12 = np.sum(np.multiply(cam_3d, proj_3d), axis=1)
    v1 = np.linalg.norm(cam_3d, axis=1)**2
    v2 = np.linalg.norm(proj_3d, axis=1)**2
    L = (np.matmul(cam_3d, origin) * v2 + np.matmul(proj_3d, -origin) * v12) / (v1 * v2 - v12**2)

    return cam_3d * L[:, None]


def undistort_cached(path, hdrs, cam_calib, proj_calib, plot=True):
    ret, cam_mtx, cam_dist, rvecs, tvecs = cam_calib
    origin, R, proj_mtx, proj_dist = proj_calib

    if hdrs is not None:
        dark, white, hor, hor_i, ver, ver_i = hdrs

        white -= dark
        hor -= dark
        hor_i -= dark
        ver -= dark
        ver_i -= dark
    else:
        white = load_openexr(path + "../checker.exr")

    h, w = white.shape[:2]
    new_cam_mtx, cam_roi = cv2.getOptimalNewCameraMatrix(cam_mtx, cam_dist, (w, h), 1, (w, h))
    print("\nnew_cam_mtx", new_cam_mtx)

    calib = {"definitions" : "https://docs.opencv.org/2.4/modules/calib3d/doc/camera_calibration_and_3d_reconstruction.html"}
    calib["new_cam_mtx"] = new_cam_mtx.tolist()

    H, W = (1080, 1920)
    new_proj_mtx, proj_roi = cv2.getOptimalNewCameraMatrix(proj_mtx, proj_dist, (W, H), 1, (W, H))
    print("\nnew_proj_mtx", new_proj_mtx)

    calib["new_proj_mtx"] = new_proj_mtx.tolist()

    n = 4
    def scale_n(img):
        return np.repeat(np.repeat(img, n, axis=0), n, axis=1)

    proj_mtx_n = proj_mtx * n
    proj_mtx_n[2, 2] = 1
    new_proj_mtx_n = new_proj_mtx * n
    new_proj_mtx_n[2, 2] = 1

    calib["new_proj_mtx_x%d" % n] = new_proj_mtx_n.tolist()
    calib["proj_origin"] = origin.tolist()
    calib["proj_origin_hint"] = "Units are millimeters (in camera's frame of reference)"
    calib["proj_basis"] = R.T.tolist()
    calib["proj_basis_hint"] = "[ex, ey, ez] in camera's frame of reference (same as origin)"

    with open(path + "calibration.json", "w") as f:
        json.dump(calib, f, indent=4)

    R, C = gen_gray((H, W), color=[255, 255, 255], invert=False)
    R_i, C_i = gen_gray((H, W), color=[255, 255, 255], invert=True)

    for i in range(11):
        break
        print(i)
        save_openexr(path + "horizontal_%d.exr" % i, cv2.undistort(hor[i, :], cam_mtx, cam_dist, None, new_cam_mtx))
        save_openexr(path + "horizontal_%d_inv.exr" % i, cv2.undistort(hor_i[i, :], cam_mtx, cam_dist, None, new_cam_mtx))

        imageio.imwrite(path + "horizontal_%d.png" % i, cv2.undistort(R[i, :], proj_mtx, proj_dist, None, new_proj_mtx))
        imageio.imwrite(path + "horizontal_%d_inv.png" % i, cv2.undistort(R_i[i, :], proj_mtx, proj_dist, None, new_proj_mtx))

        imageio.imwrite(path + "horizontal_%d_x%d.png" % (i, n), cv2.undistort(scale_n(R[i, :]), proj_mtx_n, proj_dist, None, new_proj_mtx_n))
        imageio.imwrite(path + "horizontal_%d_inv_x%d.png" % (i, n), cv2.undistort(scale_n(R_i[i, :]), proj_mtx_n, proj_dist, None, new_proj_mtx_n))

        save_openexr(path + "vertical_%d.exr" % i, cv2.undistort(ver[i, :], cam_mtx, cam_dist, None, new_cam_mtx))
        save_openexr(path + "vertical_%d_inv.exr" % i, cv2.undistort(ver_i[i, :], cam_mtx, cam_dist, None, new_cam_mtx))

        imageio.imwrite(path + "vertical_%d.png" % i, cv2.undistort(C[i, :], proj_mtx, proj_dist, None, new_proj_mtx))
        imageio.imwrite(path + "vertical_%d_inv.png" % i, cv2.undistort(C_i[i, :], proj_mtx, proj_dist, None, new_proj_mtx))

        imageio.imwrite(path + "vertical_%d_x%d.png" % (i, n), cv2.undistort(scale_n(C[i, :]), proj_mtx_n, proj_dist, None, new_proj_mtx_n))
        imageio.imwrite(path + "vertical_%d_inv_x%d.png" % (i, n), cv2.undistort(scale_n(C_i[i, :]), proj_mtx_n, proj_dist, None, new_proj_mtx_n))

    white2 = cv2.undistort(white, cam_mtx, cam_dist, None, new_cam_mtx)
    save_openexr(path + "white.exr", white2)

    checker = gen_checker((H, W), (90, 60), 100, (9, 18))
    checker2 = cv2.undistort(checker, proj_mtx, proj_dist, None, new_proj_mtx)
    imageio.imwrite(path + "checker.png", checker2)

    checker_n2 = cv2.undistort(scale_n(checker), proj_mtx_n, proj_dist, None, new_proj_mtx_n)
    imageio.imwrite(path + "checker_x%d.png" % n, checker_n2)

    if plot:
        plt.figure("White")
        plt.imshow(white2/np.max(white2), vmax=0.001)
        plt.colorbar()
        plt.tight_layout()

        plt.figure("Checker")
        plt.imshow(scale_n(checker2))
        plt.xlim([6000, 8000])
        plt.ylim([3000, 4000])
        plt.colorbar()
        plt.tight_layout()

        plt.figure("Checker_n")
        plt.imshow(checker_n2)
        plt.xlim([6000, 8000])
        plt.ylim([3000, 4000])
        plt.colorbar()
        plt.tight_layout()


if __name__ == "__main__":
    path = "shapes/"

    with open("../calibration/camera/refined_calibration.pkl", "rb") as f:
        cam_calib = pickle.load(f)

    with open("../calibration/projector/calibration.pkl", "rb") as f:
        proj_calib = pickle.load(f)

    hdrs = load_cached(path)
    # hdrs = None
    # undistort_cached(path + "undistorted/", hdrs=hdrs, cam_calib=cam_calib, proj_calib=proj_calib, plot=True)
    # plt.show()
    # exit(0)

    cam, proj = decode_cached(path, hdrs=hdrs, plot=True)

    p = triangulate(cam, proj, cam_calib, proj_calib)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(p.astype(np.float32))
    o3d.io.write_point_cloud(path + "points.ply", pcd)

    plt.figure("Reconstruction", (12, 12))
    ax = plt.subplot(111, projection='3d', proj_type='ortho')
    scatter(ax, p[::500, :].T, s=5, label="p")

    ax.set_title("Reconstruction")
    ax.set_xlabel("x, mm")
    ax.set_ylabel("z, mm")
    ax.set_zlabel("-y, mm")
    plt.tight_layout()
    axis_equal_3d(ax)

    pca = PCA(n_components=3)
    p2 = pca.fit_transform(p)

    plt.figure("PCA", (12, 9))
    for i in range(3):
        plt.subplot(3, 1, i+1)
        plt.hist(p2[:, i], bins=1000)
        mean, std = np.mean(p2[:, 2]), np.std(p2[:, 2])
        print(i, mean, std)
        plt.title("Component %d (mean = %.5f, std = %.5f)" % (i, mean, std))
        plt.xlabel("Variance, mm")
        plt.tight_layout()
        # if i == 2:
        #     plt.savefig(path + "plane_reconstruction_errors.png", dpi=160)

    plt.show()
    print("Done")
