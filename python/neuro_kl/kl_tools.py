# Author: Pietro Berkes < pietro _DOT_ berkes _AT_ googlemail _DOT_ com >
# Copyright (c) 2011 Pietro Berkes
# License: GPL v3

import scipy
from scipy import log2
from scipy.special import digamma

def kl(p, q):
    """Compute the KL divergence between two discrete probability distributions

    The calculation is done directly using the Kullback-Leibler divergence,
    KL( p || q ) = sum_{x} p(x) log_2( p(x) / q(x) )

    Base 2 logarithm is used, so that returned values is measured in bits.
    """
    
    if (p==0.).sum()+(q==0.).sum() > 0:
        raise Exception, "Zero bins found"
    return (p*(log2(p) - log2(q))).sum()

def entropy(p):
    """Compute the negative entropy of a discrete probability distribution.

    The calculation is done directly using the entropy definition,
    H(p) = sum_{x} p(x) log_2( p(x) )
    
    Base 2 logarithm is used, so that returned values is measured in bits.
    """
    
    if (p==0.).sum() > 0:
        raise Exception, "Zero bins found"
    return (p*log2(p)).sum()

def mean_H_estimate(alpha):
    """Compute the mean of a Bayesian estimator of negative entropy.

    The argument, `alpha`, contains the parameters of a Dirichlet
    posterior over a distribution, `p`. The function returns
    the mean estimation < H(p) >_P, in bits.

    Parameters:
    alpha -- parameters of the Dirichlet posterior over p
    """
    alpha0 = alpha.sum()
    res = (alpha*digamma(alpha+1)).sum()/alpha0 - digamma(alpha0+1)
    return res/log(2.)

def mean_KL_estimate(alpha, beta):
    """Compute the mean of a Bayesian estimator of KL divergence.

    The arguments, `alpha` and `beta` are the parameters of a Dirichlet
    posterior over two distributions, `p` and `q`. The function returns
    the mean estimation < < KL(p||q) >_P(alpha) >_Q(beta), in bits

    Parameters:
    alpha -- parameters of the Dirichlet posterior over p
    beta -- parameters of the Dirichlet posterior over q
    """
    
    alpha0 = alpha.sum()
    beta0 = beta.sum()
    
    res = mean_H_estimate(alpha) \
          - (alpha/alpha0*(digamma(beta) - digamma(beta0))).sum()/log(2.)
    return res

def kl_estimation(p_dict, q_dict, npoints, alpha=1., Ns=None):
    ns = array([4,2,1], dtype='int64')
    h_estimate = zeros((len(ns),))
    kl_estimate = zeros((len(ns),))
    for j, d in enumerate(ns):
        h_est = zeros((d,))
        kl_est = zeros((d,))
        for i in range(d):
            p = p_dict[d][i].flatten() # for joint distributions
            q = q_dict[d][i].flatten()
            h_est[i] = mean_H_estimate(p + alpha)
            kl_est[i] = mean_KL_estimate(p + alpha, q + alpha)
        h_estimate[j] = h_est.mean()
        kl_estimate[j] = kl_est.mean()
        
    # extrapolate
    if Ns is None:
        Ns = npoints/ns
    Ns = Ns.astype('d')
    h_extr = scipy.polyfit(Ns, Ns*Ns * h_estimate, 2)
    kl_extr = scipy.polyfit(Ns, Ns*Ns * kl_estimate, 2)
    return kl_extr[0], h_extr[0]

def h_estimation(p_dict, npoints, alpha=1., Ns=None):
    ns = array([4,2,1], dtype='int64')
    h_estimate = zeros((len(ns),))
    for j, d in enumerate(ns):
        h_est = zeros((d,))
        for i in range(d):
            p = p_dict[d][i].flatten() # for joint distributions
            h_est[i] = mean_H_estimate(p + alpha)
        h_estimate[j] = h_est.mean()
    # extrapolate
    if Ns is None:
        Ns = npoints/ns
    Ns = Ns.astype('d')
    h_extr = scipy.polyfit(Ns, Ns*Ns * h_estimate, 2)
    return h_extr[0]

# ################ DATA MANIPULATION

def spikes2states(spikes):
    """Convert a sequence of binarized spikes to a sequence of state numbers.
    """

    # check that the incoming array is binary
    if not scipy.all(scipy.logical_and(spikes>=0, spikes<=1)):
        raise ValueError('Input array must be binary')

    nchannels = spikes.shape[1]
    # convert binary sequence to decimal numbers
    pow2 = scipy.array([2**i for i in range(nchannels-1,-1,-1)])
    return (spikes*pow2).sum(axis=1)

def states2distr(states, nchannels, normed=True):
    """Return distribution over states.

    States are the decimal number of neural activity patterns, where the patterns
    are interpreted as binary words.

    E.g., if on 4 channels the activity pattern is 1 0 1 0 (spikes on
    channels 0 and 2, no spikes otherwise) the corresponding state is 10.

    See also 'spikes2states'.

    Input arguments:
    states -- array of states
    nchannels -- total number of channels (used to determine the maximum number
                 of states)
    normed -- if False return count of states, otherwise the fraction of the total

    Output:
    Array of length 2**nchannels, containing the histogram of states
    """
    bins = scipy.arange(2**nchannels+1)
    distr, ledges = scipy.histogram(states, bins=bins, normed=normed)
    return distr.astype('d')

def states2dict(all_y, nchannels, npoints, fractions=[1,2,4], shuffle=False):
    """Return dictionary with distribution over states for N, N/2, N/4.
    The distributions are *not* normalized, as required by other routines
    (e.g., KL estimation routines).
    """
    if shuffle:
        all_y = all_y.copy()
        p = scipy.random.permutation(all_y.shape[0])
        all_y = scipy.take(all_y, p)
    distr = {}
    for d in fractions:
        distr[d] = [None]*d
        block_len = npoints//d
        for i in range(d):
            part_y = all_y[i*block_len:(i+1)*block_len]
            distr[d][i] = states2distr(part_y, nchannels, normed=False)
    _check_dict_consistency(distr, npoints)
    return distr

def spikes2indep_dict(spikes, nchannels, npoints, fractions=[1,2,4]):
    """Return distribution over states, assuming that channels are independent.
    The distributions are *not* normalized, as required by other routines
    (e.g., KL estimation routines).
    """
    # p1[i] = p(channel_i = 1)
    p1 = spikes.sum(0).astype('d')/spikes.shape[0]
    # distribution over states given independence
    nbins = 2**nchannels
    indep_distr = zeros((nbins,))
    # cycle over states
    for s in range(nbins):
        # get binary pattern
        s_bin = scipy.binary_repr(s, width=nchannels) if s>0 else '0'*nchannels
        # compute probability for independent case
        prob = [(p1[k] if s_bin[k]=='1' else 1.-p1[k]) for k in range(nchannels) ]
        indep_distr[s] = scipy.prod(prob)
    # construct dictionary as for normal case
    distr = {}
    for d in fractions:
        l = npoints/d
        distr[d] = [indep_distr*l] * d
    _check_dict_consistency(distr, npoints)
    return distr

def _check_dict_consistency(distr, npoints):
    control = []
    if 2 in distr.keys(): control.append(2)
    if 4 in distr.keys(): control.append(4)
    for d in control:
        sm = 0.
        for i in range(d):
            sm += array(distr[d][i])
        assert scipy.sum(sm) - npoints < 1e-4
        assert scipy.all((sm.astype('int32') - array(distr[1][0])) < 1e-4)

def transition_matrix(y, nstates, dt=1):
    """
    Return transition matrix histogram (i.e., counts)
    """
    tr, tmp, tmp = scipy.histogram2d(y[:-dt], y[dt:], bins=range(nstates+1))
    return tr

def states2transition_dict(states, nchannels, dt=1, ds=[1,2,4], indep=False):
    """Return dictionary with transition probability distribution
    for N, N/2, N/4.
    indep -- if True, compute transition distribution assuming independence in time
    """
    npoints = states.shape[0]
    nstates = 2**nchannels
    #print 'npoints, nstates, nchannels', npoints, nstates, nchannels
    distr = {}
    for d in ds:
        distr[d] = [None]*d
        block_len = npoints/d
        for i in range(d):
            part_y = states[i*block_len:(i+1)*block_len]
            if not indep:
                # transition distribution
                distr[d][i] = transition_matrix(part_y, nstates, dt=dt)
            else:
                # distribution independent in time
                marg_distr = states2distr(part_y, nchannels)
                distr[d][i] = outer(marg_distr, marg_distr)*(part_y.shape[0]-1)
    return distr
