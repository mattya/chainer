import unittest

import numpy

import chainer
from chainer import cuda
from chainer import functions as F
from chainer import gradient_check
from chainer import testing
from chainer.utils.conv import get_deconv_outsize
from chainer.testing import attr
from chainer.testing import condition
from chainer.testing import parameterize


def _pair(x):
    if hasattr(x, '__getitem__'):
        return x
    return (x, x)


@parameterize(
    {'in_channels': 3, 'out_channels': 2, 'ksize': 3, 'stride': 2, 'pad': 1},
)
class TestDeconvolution2D(unittest.TestCase):

    def setUp(self):
        self.func = F.Deconvolution2D(
            self.in_channels, self.out_channels, self.ksize,
            stride=self.stride, pad=self.pad)
        self.func.b = numpy.random.uniform(
            -1, 1, self.func.b.shape).astype(numpy.float32)
        self.func.gW.fill(0)
        self.func.gb.fill(0)

        N = 2
        h, w = 3, 2
        kh, kw = _pair(self.ksize)
        out_h = get_deconv_outsize(h, kh, self.stride, self.pad)
        out_w = get_deconv_outsize(w, kw, self.stride, self.pad)
        self.gy = numpy.random.uniform(
            -1, 1, (N, self.out_channels, out_h, out_w)).astype(numpy.float32)
        self.x = numpy.random.uniform(
            -1, 1, (N, self.in_channels, h, w)).astype(numpy.float32)

    def check_forward_consistency(self, nobias=False):
        if nobias:
            self.func.b = None

        x_cpu = chainer.Variable(self.x)
        y_cpu = self.func(x_cpu)
        self.assertEqual(y_cpu.data.dtype, numpy.float32)

        self.func.to_gpu()
        x_gpu = chainer.Variable(cuda.to_gpu(self.x))
        y_gpu = self.func(x_gpu)
        self.assertEqual(y_gpu.data.dtype, numpy.float32)

        gradient_check.assert_allclose(y_cpu.data, y_gpu.data.get())

    @attr.cudnn
    @condition.retry(3)
    def test_forward_consistency(self):
        self.check_forward_consistency()

    @attr.cudnn
    @condition.retry(3)
    def test_forward_consistency_nobias(self):
        self.check_forward_consistency(nobias=True)

    @attr.gpu
    @condition.retry(3)
    def test_forward_consistency_im2col(self):
        self.func.use_cudnn = False
        self.check_forward_consistency()

    @attr.gpu
    @condition.retry(3)
    def test_forward_consistency_im2col_nobias(self):
        self.func.use_cudnn = False
        self.check_forward_consistency(nobias=True)

    def check_backward(self, x_data, y_grad, nobias=True):
        x = chainer.Variable(x_data)
        y = self.func(x)
        y.grad = y_grad
        y.backward()

        func = y.creator

        if nobias:
            f = lambda: func.forward((x.data,))
            gx, gW = gradient_check.numerical_grad(
                f, (x.data, func.W), (y.grad,), eps=1e-2)
        else:
            f = lambda: func.forward((x.data,))
            gx, gW, gb = gradient_check.numerical_grad(
                f, (x.data, func.W, func.b), (y.grad,), eps=1e-2)

        gradient_check.assert_allclose(gx, x.grad)
        gradient_check.assert_allclose(gW, func.gW)
        if not nobias:
            gradient_check.assert_allclose(gb, func.gb)

    @condition.retry(3)
    def test_backward_cpu(self):
        self.check_backward(self.x, self.gy)

    @condition.retry(3)
    def test_backward_cpu_nobias(self):
        self.check_backward(self.x, self.gy, nobias=True)

    @attr.cudnn
    @condition.retry(3)
    def test_backward_gpu(self):
        self.func.to_gpu()
        self.check_backward(cuda.to_gpu(self.x), cuda.to_gpu(self.gy))

    @attr.cudnn
    @condition.retry(3)
    def test_backward_gpu_nobias(self):
        self.func.to_gpu()
        self.check_backward(cuda.to_gpu(self.x), cuda.to_gpu(self.gy),
                            nobias=True)

    @attr.gpu
    @condition.retry(3)
    def test_backward_gpu_im2col(self):
        self.func.use_cudnn = False
        self.func.to_gpu()
        self.check_backward(cuda.to_gpu(self.x), cuda.to_gpu(self.gy))

    @attr.gpu
    @condition.retry(3)
    def test_backward_gpu_im2col_nobias(self):
        self.func.use_cudnn = False
        self.func.to_gpu()
        self.check_backward(cuda.to_gpu(self.x), cuda.to_gpu(self.gy),
                            nobias=True)

testing.run_module(__name__, __file__)