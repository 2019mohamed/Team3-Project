"""
TartanAir Multi Dataset Loader
http://www.cvlibs.net/datasets/kitti/eval_semseg.php?benchmark=semantics2015
"""

import os
import sys
import numpy as np
from PIL import Image
from torch.utils import data
import logging
import datasets.uniform as uniform
import datasets.tartanair_labels as tartanair_labels
import json
from config import cfg

import random

trainid_to_name = tartanair_labels.trainId2name
id_to_trainid1 = tartanair_labels.label2trainid
id_to_trainid2 = {0:0, 1:1}
num_classes = 30
num_classes1 = 30
num_classes2 = 2
ignore_label = 255
root = cfg.DATASET.TARTANAIR_DIR_RGB
root1 = cfg.DATASET.TARTANAIR_DIR_SEMANTIC
root2 = cfg.DATASET.TARTANAIR_DIR_TRAV
num_images = 2140

palette = [128, 64, 128, 244, 35, 232, 70, 70, 70, 102, 102, 156, 190, 153, 153,
           153, 153, 153, 250, 170, 30,
           220, 220, 0, 107, 142, 35, 152, 251, 152, 70, 130, 180, 220, 20, 60,
           255, 0, 0, 0, 0, 142, 0, 0, 70,
           0, 60, 100, 0, 80, 100, 0, 0, 230, 119, 11, 32]
zero_pad = 256 * 3 - len(palette)
for i in range(zero_pad):
    palette.append(0)

def colorize_mask(mask):
    # mask: numpy array of the mask
    new_mask = Image.fromarray(mask.astype(np.uint8)).convert('P')
    new_mask.putpalette(palette)
    return new_mask

def get_train_val(cv_split, all_items):
    # 90/10 train/val split, three random splits for cross validation
    val_0 = [1,5,11,29,35,49,57,68,72,82,93,115,119,130,145,154,156,167,169,189,198]
    val_1 = [0,12,24,31,42,50,63,71,84,96,101,112,121,133,141,155,164,171,187,191,197]
    #val_2 = [3,6,13,21,41,54,61,73,88,91,110,121,126,131,142,149,150,163,173,183,199]
    val_2 = random.sample(range(num_images), int(0.1 * num_images))

    train_set = []
    val_set = []

    if cv_split == 0:
        for i in range(num_images):
            if i in val_0:
                val_set.append(all_items[i])
            else:
                train_set.append(all_items[i])
    elif cv_split == 1:
        for i in range(num_images):
            if i in val_1:
                val_set.append(all_items[i])
            else:
                train_set.append(all_items[i])
    elif cv_split == 2:
        for i in range(num_images):
            if i in val_2:
                val_set.append(all_items[i])
            else:
                train_set.append(all_items[i])
    else:
        logging.info('Unknown cv_split {}'.format(cv_split))
        sys.exit()

    return train_set, val_set

def make_dataset(img_path, mask_path, mask2_path, mode, maxSkip=0, cv_split=0, hardnm=0):
    items = []
    all_items = []
    aug_items = []

    #assert quality == 'semantic'
    assert mode in ['train', 'val', 'trainval']
    # note that train and val are randomly determined, no official split

    #img_dir_name = "training"
    #img_path = os.path.join(root, img_dir_name, 'image_2')
    #mask_path = os.path.join(root, img_dir_name, 'semantic')

    c_items = os.listdir(img_path)
    c_items.sort()

    for it in c_items:
        item = (os.path.join(img_path, it), os.path.join(mask_path, it), os.path.join(mask2_path, it))
        all_items.append(item)
    logging.info('TartanAir has a total of {} images'.format(len(all_items)))

    # split into train/val
    train_set, val_set = get_train_val(cv_split, all_items)

    if mode == 'train':
        items = train_set
    elif mode == 'val':
        items = val_set
    elif mode == 'trainval':
        items = train_set + val_set
    else:
        logging.info('Unknown mode {}'.format(mode))
        sys.exit()

    # unpack two tasks
    items1 = []
    items2 = []
    for it in items:
        items1.append((it[0], it[1]))
        items2.append((it[0], it[2]))
    logging.info('TantanAir-{}: {} images'.format(mode, len(items)))
    
    return items1, items2

def make_test_dataset(quality, mode, maxSkip=0, cv_split=0):
    items = []
    assert quality == 'semantic'
    assert mode == 'test'

    img_dir_name = "testing"
    img_path = os.path.join(root, img_dir_name, 'image_2')

    c_items = os.listdir(img_path)
    c_items.sort()
    for it in c_items:
        item = (os.path.join(img_path, it), None)
        items.append(item)
    logging.info('KITTI has a total of {} test images'.format(len(items)))

    return items, []

class TartanAir_Multi(data.Dataset):

    def __init__(self, quality, mode, maxSkip=0, joint_transform_list=None,
                 transform=None, target_transform=None, dump_images=False,
                 class_uniform_pct=0, class_uniform_tile=0, test=False,
                 cv_split=None, scf=None, hardnm=0):

        self.quality = quality
        self.mode = mode
        self.maxSkip = maxSkip
        self.joint_transform_list = joint_transform_list
        self.transform = transform
        self.target_transform = target_transform
        self.dump_images = dump_images
        self.class_uniform_pct = class_uniform_pct
        self.class_uniform_tile = class_uniform_tile
        self.scf = scf
        self.hardnm = hardnm

        if cv_split:
            self.cv_split = cv_split
            assert cv_split < cfg.DATASET.CV_SPLITS, \
                'expected cv_split {} to be < CV_SPLITS {}'.format(
                    cv_split, cfg.DATASET.CV_SPLITS)
        else:
            self.cv_split = 0

        if self.mode == 'test':
            self.imgs, _ = make_test_dataset(quality, mode, self.maxSkip, cv_split=self.cv_split)
        else:
            self.imgs1, self.imgs2 = make_dataset(root, root1, root2, mode, self.maxSkip, cv_split=self.cv_split, hardnm=self.hardnm)
            assert len(self.imgs1), 'Found 0 images, please check the data set'

        # Centroids for GT data
        if self.class_uniform_pct > 0:
            if self.scf:
                json_fn1 = 'tartanair_multi_tile{}_cv{}_scf1.json'.format(self.class_uniform_tile, self.cv_split)
                json_fn2 = 'tartanair_multi_tile{}_cv{}_scf2.json'.format(self.class_uniform_tile, self.cv_split)
            else:
                json_fn1 = 'tartanair_multi_tile{}_cv{}_{}_hardnm{}1.json'.format(self.class_uniform_tile, self.cv_split, self.mode, self.hardnm)
                json_fn2 = 'tartanair_multi_tile{}_cv{}_{}_hardnm{}2.json'.format(self.class_uniform_tile, self.cv_split, self.mode, self.hardnm)
            if os.path.isfile(json_fn1):
                with open(json_fn1, 'r') as json_data:
                    centroids1 = json.load(json_data)
                self.centroids1 = {int(idx): centroids1[idx] for idx in centroids1}
                with open(json_fn2, 'r') as json_data:
                    centroids2 = json.load(json_data)
                self.centroids2 = {int(idx): centroids2[idx] for idx in centroids2}
            else:
                if self.scf:
                    self.centroids1 = kitti_uniform.class_centroids_all(
                        self.imgs1,
                        num_classes1,
                        id2trainid=id_to_trainid1,
                        tile_size=class_uniform_tile)
                    self.centroids2 = kitti_uniform.class_centroids_all(
                        self.imgs2,
                        num_classes2,
                        id2trainid=id_to_trainid2,
                        tile_size=class_uniform_tile)
                else:
                    self.centroids1 = uniform.class_centroids_all(
                        self.imgs1,
                        num_classes1,
                        id2trainid=id_to_trainid1,
                        tile_size=class_uniform_tile)
                    self.centroids2 = uniform.class_centroids_all(
                        self.imgs2,
                        num_classes2,
                        id2trainid=id_to_trainid2,
                        tile_size=class_uniform_tile)
                with open(json_fn1, 'w') as outfile:
                    json.dump(self.centroids1, outfile, indent=4)
                with open(json_fn2, 'w') as outfile:
                    json.dump(self.centroids2, outfile, indent=4)

        self.build_epoch()

    def build_epoch(self, cut=False):
        if self.class_uniform_pct > 0:
            self.imgs_uniform1 = uniform.build_epoch(self.imgs1,
                                                    self.centroids1,
                                                    num_classes1,
                                                    cfg.CLASS_UNIFORM_PCT)
            self.imgs_uniform2 = uniform.build_epoch(self.imgs2,
                                                    self.centroids2,
                                                    num_classes2,
                                                    cfg.CLASS_UNIFORM_PCT)
        else:
            self.imgs_uniform1 = self.imgs1
            self.imgs_uniform2 = self.imgs2

    def __getitem__(self, index):
        elem1 = self.imgs_uniform1[index]
        elem2 = self.imgs_uniform2[index]
        centroid1 = None
        centroid2 = None

        if len(elem1) == 4:
            img_path1, mask_path1, centroid1, class_id1 = elem1
        else:
            img_path1, mask_path1 = elem1
        if len(elem2) == 4:
            img_path2, mask_path2, centroid2, class_id2 = elem2
        else:
            img_path2, mask_path2 = elem2

        if self.mode == 'test':
            img, mask = Image.open(img_path).convert('RGB'), None
        else:
            img1, mask1 = Image.open(img_path1).convert('RGB'), Image.open(mask_path1)
            img2, mask2 = Image.open(img_path2).convert('RGB'), Image.open(mask_path2)
        img_name1 = os.path.splitext(os.path.basename(img_path1))[0]
        img_name2 = os.path.splitext(os.path.basename(img_path2))[0]

        # kitti scale correction factor
        if self.mode == 'train' or self.mode == 'trainval':
            if self.scf:
                width1, height1 = img1.size
                width2, height2 = img2.size
                img1 = img1.resize((width1*2, height1*2), Image.BICUBIC)
                img2 = img2.resize((width2*2, height2*2), Image.BICUBIC)
                mask1 = mask1.resize((width1*2, height1*2), Image.NEAREST)
                mask2 = mask2.resize((width2*2, height2*2), Image.NEAREST)
        elif self.mode == 'val':
            width, height = 640, 480
            img1 = img1.resize((width, height), Image.BICUBIC)
            img2 = img2.resize((width, height), Image.BICUBIC)
            mask1 = mask1.resize((width, height), Image.NEAREST)
            mask2 = mask2.resize((width, height), Image.NEAREST)
        elif self.mode == 'test':
            img_keepsize = img.copy()
            width, height = 1280, 384
            img = img.resize((width, height), Image.BICUBIC)
        else:
            logging.info('Unknown mode {}'.format(mode))
            sys.exit()

        if self.mode != 'test':
            mask1 = np.array(mask1)
            mask2 = np.array(mask2)
            mask_copy1 = mask1.copy()
            mask_copy2 = mask2.copy()

            for k, v in id_to_trainid1.items():
                mask_copy1[mask1 == k] = v
            for k, v in id_to_trainid2.items():
                mask_copy2[mask2 == k] = v
            mask1 = Image.fromarray(mask_copy1.astype(np.uint8))
            mask2 = Image.fromarray(mask_copy2.astype(np.uint8))

        # Image Transformations
        if self.joint_transform_list is not None:
            for idx, xform in enumerate(self.joint_transform_list):
                if idx == 0 and centroid1 is not None:
                    # HACK
                    # We assume that the first transform is capable of taking
                    # in a centroid
                    img1, mask1 = xform(img1, mask1, centroid1)
                else:
                    img1, mask1 = xform(img1, mask1)
                if idx == 0 and centroid2 is not None:
                    # HACK
                    # We assume that the first transform is capable of taking
                    # in a centroid
                    img2, mask2 = xform(img2, mask2, centroid2)
                else:
                    img2, mask2 = xform(img2, mask2)

        # Debug
        '''if self.dump_images and centroid is not None:
            outdir = './dump_imgs_{}'.format(self.mode)
            os.makedirs(outdir, exist_ok=True)
            dump_img_name = trainid_to_name[class_id] + '_' + img_name
            out_img_fn = os.path.join(outdir, dump_img_name + '.png')
            out_msk_fn = os.path.join(outdir, dump_img_name + '_mask.png')
            mask_img = colorize_mask(np.array(mask))
            img.save(out_img_fn)
            mask_img.save(out_msk_fn)'''

        if self.transform is not None:
            img1 = self.transform(img1)
            img2 = self.transform(img2)
            if self.mode == 'test':
                img_keepsize = self.transform(img_keepsize)
                mask = img_keepsize
        if self.target_transform is not None:
            if self.mode != 'test':
                mask1 = self.target_transform(mask1)
                mask2 = self.target_transform(mask2)

        return img1, mask1, img_name1, img2, mask2, img_name2

    def __len__(self):
        return len(self.imgs_uniform1)
