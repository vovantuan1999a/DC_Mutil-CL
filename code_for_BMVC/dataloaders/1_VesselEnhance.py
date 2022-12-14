"""
Sato: https://www.kite.com/python/docs/skimage.filters.sato
"""

import glob
import os
import re
import numpy as np
import SimpleITK as sitk

# ROI bounding box extract lib
from skimage.measure import label
from skimage.measure import regionprops

# Preprocess Vessel
from skimage.filters import frangi, hessian, sato, meijering



def findidx(file_name):
    # find the idx
    cop = re.compile("[^0-9]")
    idx = cop.sub('', file_name)
    return idx

def combine_vessel_mask(mask1, mask2):
    mask = mask1 + mask2
    mask[mask >= 1] = 1
    return mask

def liver_ROI(mask_npy):
    # regionprops tutorial: https://scikit-image.org/docs/dev/auto_examples/segmentation/plot_regionprops.html
    labeled_img, num = label(mask_npy, return_num=True)
    print(labeled_img.shape)
    print('There are {} regions'.format(num))
    # print(np.max(labeled_img))
    if num > 0:
        regions = regionprops(labeled_img, cache=True)
        for prop in regions:
            box = prop.bbox #Bounding box (min_row, min_col, max_row, max_col)
            area = prop.area #Number of pixels of the region
            ratio = prop.extent #Ratio of pixels in the region to pixels in the total bounding box. Computed as area / (rows * cols)
            print(box)
            print(area)
            print(ratio)
            # print(centroid)
            if area >= 500:
                return box

def crop_ROI(npy_data, box):
    xmin, xmax = box[1], box[4]
    ymin, ymax = box[2], box[5]
    zmin, zmax = box[0], box[3]
    # crop to z x 320 x 320
    for i in range(0,20,5):
        npy_data_aftercrop = npy_data[zmin:zmax, xmin-i:xmin+320 -i, ymin-i:ymin+320 - i]
#         npy_data_aftercrop = npy_data[zmin:zmax, xmin-5:xmin+315, ymin-5:ymin+315]
#     print('X ',xmin - 5,xmin + 315)
#     print('Y ',ymin - 5,ymin + 315)
        print('Propose crop size:', npy_data_aftercrop.shape)
        if npy_data_aftercrop.shape[1] == 320 and npy_data_aftercrop.shape[2] == 320:
            break
        else:
            print('***************************************ERROR CASE*****************************************')
    print('Final crop size ',npy_data_aftercrop.shape)
    return npy_data_aftercrop

# val volume h5 generate
def ROI_crop_preprocess(val_img_Dir, msk_baseDir, vessel_msk_baseDir):
    val_img_path = sorted(glob.glob(val_img_Dir))
    for case in val_img_path:
        print(case)
        img_itk = sitk.ReadImage(case)
        # origin = img_itk.GetOrigin()
        spacing = img_itk.GetSpacing()
        # direction = img_itk.GetDirection()

        # Resampling the img to 1x1x1
        # img_itk, new_spacing = Resampling(img_itk, label=False)
        image = sitk.GetArrayFromImage(img_itk)
        # change to mask path
#         idx = findidx(case)
        idx = findidx(case.split('/')[-1])
        label_file_name = 'patient_' + str(idx)[:] + '.nii'
        msk_path = os.path.join(msk_baseDir, label_file_name)
        print(msk_path)
        vessel_msk_path = os.path.join(vessel_msk_baseDir, label_file_name)
#         vessel_msk2_path = os.path.join(vessel_msk2_baseDir, label_file_name)
        # msk_path = case.replace(".nii.gz", "_gt.nii.gz")
        if os.path.exists(msk_path):
            print(msk_path)
            msk_itk = sitk.ReadImage(msk_path)
            # resampling label
            # msk_itk, new_spacing = Resampling(msk_itk, label=True)
            mask_ = sitk.GetArrayFromImage(msk_itk)
            if np.max(mask_) == 255: # fix the bug that some labels are valued 1 not 255
                mask = mask_ / 255 #fix the bug that did not find the region using normalized masks
            else:
                mask = mask_

            vesselmsk_itk = sitk.ReadImage(vessel_msk_path)
            #resampling label
            # vesselmsk1_itk, new_spacing = Resampling(vesselmsk1_itk, label=True)
            vessel_mask = sitk.GetArrayFromImage(vesselmsk_itk)
            if np.max(vessel_mask) == 255:
                vessel_mask = vessel_mask / 255

#             vesselmsk2_itk = sitk.ReadImage(vessel_msk2_path)
#             # resampling label
#             # vesselmsk2_itk, new_spacing = Resampling(vesselmsk2_itk, label=True)
#             vessel_mask2 = sitk.GetArrayFromImage(vesselmsk2_itk)
#             if np.max(vessel_mask2) == 255:
#                 vessel_mask2 = vessel_mask2 / 255
#             # combine two vessel labels
#             vessel_mask = combine_vessel_mask(vessel_mask1, vessel_mask2)

            print('mask shape:', mask.shape)

            # mask the liver?
            image = mask * image
            vessel_mask = mask * vessel_mask

            # Vessel Enhancement
            image = VesselEnhance(image, type='sato')
            # Normalize
            image = normalize_after_prob(image)

            # crop the liver area
            box = liver_ROI(mask_)  #(xmin, ymin, zmin, xmax, ymax, zmax)
            # start cropping
            image = crop_ROI(image, box)
            mask = crop_ROI(mask, box)
            vessel_mask = crop_ROI(vessel_mask, box)

            item = case.split("/")[-1].split(".")[0]
            if image.shape != mask.shape:
                print("Error")
            print(item)
            print('---------------')
            img_itk = sitk.GetImageFromArray(image.astype(np.float32))
            img_itk.SetSpacing(spacing)
            label_itk = sitk.GetImageFromArray(mask.astype(np.float32))
            label_itk.SetSpacing(spacing)
            vessel_label_itk = sitk.GetImageFromArray(vessel_mask.astype(np.float32))
            vessel_label_itk.SetSpacing(spacing)
            sitk.WriteImage(img_itk, '../data/IRCAD_NEW/image_ROI/image_{}.nii.gz'.format(str(idx)))
            sitk.WriteImage(vessel_label_itk,
                            '../data/IRCAD_NEW/label_vessel_ROI/image_{}_gt.nii.gz'.format(str(idx)))
    print("Converted val IRCAD volumes to ROI")


    
def ROI_crop_preprocess_M(val_img_Dir, msk_baseDir, vessel_msk_baseDir):
    val_img_path = sorted(glob.glob(val_img_Dir))
    for case in val_img_path:
        print(case)
        img_itk = sitk.ReadImage(case)
        # origin = img_itk.GetOrigin()
        spacing = img_itk.GetSpacing()
        # direction = img_itk.GetDirection()

        # Resampling the img to 1x1x1
        # img_itk, new_spacing = Resampling(img_itk, label=False)
        image = sitk.GetArrayFromImage(img_itk)
        # change to mask path
#         idx = findidx(case)
        idx = findidx(case.split('/')[-1])
        label_file_name = 'patient_' + str(idx)[:] + '.nii'
        msk_path = os.path.join(msk_baseDir, label_file_name)
        print(msk_path)
        vessel_msk_path = os.path.join(vessel_msk_baseDir, label_file_name)
#         vessel_msk2_path = os.path.join(vessel_msk2_baseDir, label_file_name)
        # msk_path = case.replace(".nii.gz", "_gt.nii.gz")
        if os.path.exists(msk_path):
            print(msk_path)
            msk_itk = sitk.ReadImage(msk_path)
            # resampling label
            # msk_itk, new_spacing = Resampling(msk_itk, label=True)
            mask_ = sitk.GetArrayFromImage(msk_itk)
            if np.max(mask_) == 255: # fix the bug that some labels are valued 1 not 255
                mask = mask_ / 255 #fix the bug that did not find the region using normalized masks
            else:
                mask = mask_

            vesselmsk_itk = sitk.ReadImage(vessel_msk_path)
            #resampling label
            # vesselmsk1_itk, new_spacing = Resampling(vesselmsk1_itk, label=True)
            vessel_mask = sitk.GetArrayFromImage(vesselmsk_itk)
            if np.max(vessel_mask) == 255:
                vessel_mask = vessel_mask / 255

#             vesselmsk2_itk = sitk.ReadImage(vessel_msk2_path)
#             # resampling label
#             # vesselmsk2_itk, new_spacing = Resampling(vesselmsk2_itk, label=True)
#             vessel_mask2 = sitk.GetArrayFromImage(vesselmsk2_itk)
#             if np.max(vessel_mask2) == 255:
#                 vessel_mask2 = vessel_mask2 / 255
#             # combine two vessel labels
#             vessel_mask = combine_vessel_mask(vessel_mask1, vessel_mask2)

            print('mask shape:', mask.shape)

            # mask the liver?
            image = mask * image
            vessel_mask = mask * vessel_mask

            # Vessel Enhancement
            image = VesselEnhance(image, type='meijering')
            # Normalize
            image = normalize_after_prob(image)

            # crop the liver area
            box = liver_ROI(mask_)  #(xmin, ymin, zmin, xmax, ymax, zmax)
            # start cropping
            image = crop_ROI(image, box)
            mask = crop_ROI(mask, box)
            vessel_mask = crop_ROI(vessel_mask, box)

            item = case.split("/")[-1].split(".")[0]
            if image.shape != mask.shape:
                print("Error")
            print(item)
            print('---------------')
            img_itk = sitk.GetImageFromArray(image.astype(np.float32))
            img_itk.SetSpacing(spacing)
            label_itk = sitk.GetImageFromArray(mask.astype(np.float32))
            label_itk.SetSpacing(spacing)
            vessel_label_itk = sitk.GetImageFromArray(vessel_mask.astype(np.float32))
            vessel_label_itk.SetSpacing(spacing)
            sitk.WriteImage(img_itk, '../../data/IRCAD_NEW_M/image_ROI/image_{}.nii.gz'.format(str(idx)))
            sitk.WriteImage(vessel_label_itk,
                            '../../data/IRCAD_NEW_M/label_vessel_ROI/image_{}_gt.nii.gz'.format(str(idx)))
    print("Converted val IRCAD volumes to ROI")
# Preprocessing Library
def normalize_after_prob(nii_data):
    """
    normalize
    Our values currently range from -1024 to around 500.
    Anything above 400 is not interesting to us,
    as these are simply bones with different radiodensity.
    """
    # Default: [0, 400]
    MIN_BOUND = np.min(nii_data)
    MAX_BOUND = np.max(nii_data)

    nii_data = (nii_data - MIN_BOUND) / (MAX_BOUND - MIN_BOUND)
    nii_data[nii_data > 1] = 1.
    nii_data[nii_data < 0] = 0.
    return nii_data


def VesselEnhance(img, type):
    if type == 'sato':
        filter_img = sato(img, sigmas=range(1, 3, 1), black_ridges=False, mode='constant')
    elif type == 'frangi':
        filter_img = frangi(img, sigmas=range(1, 4, 1), scale_range=None,
                            scale_step=None, alpha=0.5, beta=0.5, gamma=5, black_ridges=False, mode='constant', cval=1)
    elif type == 'meijering':
        filter_img = meijering(img, sigmas=range(1, 4, 1), alpha=0.5, black_ridges=False, mode='constant', cval=1)
    return filter_img


if __name__=='__main__':

    os.environ["CUDA_VISIBLE_DEVICES"] = "1"

#     train_img_Dir = '../../data/IRCAD/train_image/*.nii.gz'
#     val_img_Dir = '../../data/IRCAD/val_image/*.nii.gz'
#     test_img_Dir = '../../data/IRCAD/test_image/*.nii.gz'

    # liver
    ROI_baseDir = '/workspace/vinbrain/namnguyen/arterial_liver_segmentation/dataset/3DIRCADb/liver/'
    vessel_msk_baseDir = '/workspace/vinbrain/namnguyen/arterial_liver_segmentation/dataset/3DIRCADb/vessel/'
#     vessel_msk1_baseDir = '../../data/IRCAD/label_venacava/'
#     vessel_msk2_baseDir = '../../data/IRCAD/label_portalvein/'
    organ = 'vessel'

    # single case process seperately
    all_img_Dir = '/workspace/vinbrain/namnguyen/arterial_liver_segmentation/dataset/3DIRCADb/images/*'
    
#     ROI_crop_preprocess(all_img_Dir, ROI_baseDir, vessel_msk_baseDir)
    
    ROI_crop_preprocess_M(all_img_Dir, ROI_baseDir, vessel_msk_baseDir)


    ## crop ROI region
    # # train process
    # ROI_crop_preprocess(train_img_Dir, ROI_baseDir, vessel_msk1_baseDir, vessel_msk2_baseDir, organ, mode='train')
    #
    # # val process
    # ROI_crop_preprocess(val_img_Dir, ROI_baseDir, vessel_msk1_baseDir, vessel_msk2_baseDir, organ, mode='val')
    #
    # # test process
    # ROI_crop_preprocess(test_img_Dir, ROI_baseDir, vessel_msk1_baseDir, vessel_msk2_baseDir, organ, mode='test')

    ## single case process seperately (case 16)
    # problem_img_Dir = '../../data/IRCAD/problem_img/*.nii.gz'
    # ROI_crop_preprocess(problem_img_Dir, ROI_baseDir, vessel_msk1_baseDir, vessel_msk2_baseDir, organ, mode='val')

