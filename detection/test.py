import os
import numpy as np
import tensorflow as tf
import config_utils as config
import data_utils as data_utils
import tf_extended as tfe

from nets import STVNet

os.environ["CUDA_VISIBLE_PATH"] = "0"
model_dir='/home/hcxiao/Codes/YARR/detection/models/'
STV2K_Path = '/media/data2/hcx_data/STV2K/stv2k_train/'
img_name = 'STV2K_tr_0001.jpg'
default_size = STVNet.default_params.img_shape
input_size = default_size
# gpu_list = config.FLAGS.gpu_list.split(',')
# gpus = [int(gpu_list[i]) for i in range(len(gpu_list))]

def get_image(img_path):
    im = Image.open(img_path)
    im = im.resize(input_size)
    im = np.array(im)
    # img_input = tf.to_float(tf.convert_to_tensor(im))

    return im

def convert_poly_to_bbox(polys):
    bboxes = []
    for poly in polys:
        (x1, y1, x2, y2, x3, y3, x4, y4) = poly
        x = [x1, x2, x3, x4]
        y = [y1, y2, y3, y4]
        xmin = min(x) / input_size[0]
        xmax = max(x) / input_size[0]
        ymin = min(y) / input_size[1]
        ymax = max(y) / input_size[1]

        if xmin < 0:
            xmin = 0
        if ymin < 0:
            ymin = 0

        bbox = [ymin, xmin, ymax, xmax]
        bboxes.append(bbox)
    return bboxes

def test(img_name):
    tf.logging.set_verbosity(tf.logging.INFO)
    with tf.Graph().as_default():
        im = get_image(STV2K_Path + img_name)
        polys,_ = data_utils.load_annotation(STV2K_Path + img_name.replace('.jpg', '.txt'))

        label = tf.placeholder(tf.int64, shape=[None], name='labels')
        bboxes = tf.placeholder(tf.float32, shape=[None, 4], name='bboxes')
        inputs = tf.placeholder(tf.float32, shape=[None, None, None, 3], name='inputs')
        b_gdifficults = tf.zeros(tf.shape(label), dtype=tf.int64)

        anchors = STVNet.ssd_anchors_all_layers()
        predictions, localisations, logits, end_points = STVNet.model(inputs)
        gclasses, glocal, gscores = STVNet.tf_ssd_bboxes_encode(label, bboxes, anchors)
        pos_loss, neg_loss, loc_loss = STVNet.ssd_losses(logits, localisations, gclasses, glocal, gscores)

        pre_locals = STVNet.tf_ssd_bboxes_encode(localisations, anchors, scope='bboxes_decode')
        pre_scores, pre_bboxes = STVNet.detected_bboxes(predictions, pre_locals,
                                                        select_threshold=config.FLAGS.select_threshold,
                                                        nms_threshold=config.FLAGS.nms_threshold,
                                                        clipping_bbox=None,
                                                        top_k=config.FLAGS.select_top_k,
                                                        keep_top_k=config.FLAGS.keep_top_k)

        num_gbboxes, tp, fp, rscores = \
                tfe.bboxes_matching_batch(rscores.keys(), pre_scores, pre_bboxes,
                                          label, bboxes, b_gdifficults,
                                          matching_threshold=config.FLAGS.matching_threshold)

    saver = tf.train.Saver()
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        sess.run(tf.local_variables_initializer())
        
        saver.restore(sess, model_dir + 'stvnet.ckpt')

        gt_bboxes = convert_poly_to_bbox(polys)
        gt_labels = [1 for i in range(len(gt_bboxes))]

        pre_s, pre_box, p_loss, n_loss, lc_loss = sess.run([pre_scores, pre_bboxes, pos_loss, neg_loss, loc_loss],
                                                              feed_dict={inputs=[im],
                                                                         label=gt_labels,
                                                                         bboxes=gt_bboxes})
        # img = np.copy(im)
        # bboxes_draw_on_img(img, pre_c, pre_s, pre_box, [(255, 255, 255), (31, 119, 180)])
        # fig = plt.figure(figsize=(12, 12))
        # plt.imshow(img)
        print('pre-score: ', pre_s)
        print('pre-boxes: ', pre_box)
        print('postive loss: ', p_loss)
        print('negtive loss: ', n_loss)
        print('localisation loss: ', lc_loss)

        
def bboxes_draw_on_img(img, classes, scores, bboxes, colors, thickness=2):
    shape = img.shape
    for i in range(bboxes.shape[0]):
        bbox = bboxes[i]
        color = colors[classes[i]]
        # Draw bounding box...
        p1 = (int(bbox[0] * shape[0]), int(bbox[1] * shape[1]))
        p2 = (int(bbox[2] * shape[0]), int(bbox[3] * shape[1]))
        cv2.rectangle(img, p1[::-1], p2[::-1], color, thickness)
        # Draw text...
        s = '%s/%.3f' % (classes[i], scores[i])
        p1 = (p1[0]-5, p1[1])
        cv2.putText(img, s, p1[::-1], cv2.FONT_HERSHEY_DUPLEX, 0.4, color, 1)


if __name__ == '__main__':
    test()
    

