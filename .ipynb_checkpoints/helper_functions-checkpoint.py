import re
import pandas as pd
import numpy as np
import cufflinks as cf
from plotly.subplots import make_subplots
import plotly.graph_objs as go
import plotly.express as px
from scipy.optimize import curve_fit
from scipy.stats import iqr
from scipy.stats import norm


def load_file(path):
    '''
    This function will parse a standard HEKA .asc file into a pandas dataframe.

    Arguments: 
    path - a stringIO input of a standard HEKA output .asc file.

    Returns:
    df, dfcache - two copies of the file reformatted into a dataframe.
    '''

    lineIndices = []            
    
    # Splits string at \n and removes trailing spaces  
    with open(path, "r") as f:                        
        rawFile = f.read().strip().split("\n")         

    count=0          
    # Finds rows that contain header information to exclude from df                                     
    for line in rawFile:                                  
        if re.search(r"[a-z]+", line) == None:           
            lineIndices.append(count)                     
        count += 1                                    
    
    # Formats headerless file for later df
    processedFile = [rawFile[i].strip().replace(" ", "").split(",") for i in lineIndices]     

    # Use the difference in file with and without headers to find nSweeps
    nSweeps = int((len(rawFile)-len(processedFile)-1)/2)   

    if len(processedFile[0]) == 5:
        colnames = ['index','ti','i','tp','p']
    else:
        colnames = ['index','ti','i','tp','p','tv','v']

    df = pd.DataFrame(columns=colnames, data=processedFile)
    df = df.apply(pd.to_numeric)
    df = df.dropna(axis=0)

    # Make new column with sweep identity
    df['sweep'] = np.repeat(np.arange(nSweeps) + 1, len(df)/nSweeps)
    
    # Change units to something easier to work with
    df['p'] = df['p'] / 0.02
    df['ti'] *= 1000
    df['i'] *= 1e12
    df['tp'] *= 1000

    return df

def plot_sweeps(df):
    '''
    This function will plot a dataframe of sweeps using plotly with hidden axis.

    Arguments: 
    df - a dataframe with columns tp, p, ti, i, and sweep

    Returns:
    fig - a plotly figure object
    '''

    fig = make_subplots(rows=2, cols=1,  row_width=[0.6, 0.3])
    
    for name, sweep in df.groupby('sweep'):
        
        fig.add_trace(
            go.Scatter(mode='lines', name=name, x=sweep.tp, y=sweep.p, marker=dict(color='#800000'),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'),
            row=1, col=1)
            
        fig.add_trace(
            go.Scatter(mode='lines', name=name, x=sweep.ti, y=sweep.i, marker=dict(color='black'),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'),
            row=2, col=1)

    fig.update_layout(
        height=400,
        width=600,
        template='none',
        xaxis_showticklabels=False,
        xaxis_showgrid=False,
        yaxis_showticklabels=False,
        yaxis_showgrid=False,
        xaxis2_showticklabels=False,
        xaxis2_showgrid=False,
        yaxis2_showticklabels=False,
        yaxis2_showgrid=False,
        showlegend=False,
        hovermode='closest')

    fig.update_xaxes(matches='x')

    return(fig)

def plot_sweeps_stacked(df):
    '''
    This function will plot a dataframe of sweeps using plotly with hidden axis.

    Arguments: 
    df - a dataframe with columns tp, p, ti, i, and sweep

    Returns:
    fig - a plotly figure object
    '''
    nsweeps = len(np.unique(df.sweep))

    fig = make_subplots(rows=nsweeps + 1, cols=1,  row_width=[1/(nsweeps + 1) for i in range(nsweeps + 1)])
    
    for name, sweep in df.groupby('sweep'):
        
        fig.add_trace(
            go.Scatter(mode='lines', name=name, x=sweep.tp, y=sweep.p, marker=dict(color='#800000'),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'),
            row=1, col=1)
            
        fig.add_trace(
            go.Scatter(mode='lines', name=name, x=sweep.ti, y=sweep.i, marker=dict(color='black'),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'),
            row= int(np.unique(sweep.sweep)) + 1, col=1)

    fig.update_layout(
        height=800,
        width=800,
        template='none',
        showlegend=False,
        hovermode='closest')

    fig.update_xaxes(matches='x')

    return(fig)

def add_scalebars(df, fig, locs):
    '''
    This function will add scalebars to a plot.

    Arguments: 
    df - a pandas dataframe with columns p, ti, tp, and i.
    fig - a plotly figure object..
    locs - a dictionary with the axis names as keys and scalebar limits as values.

    Returns:
    fig - a plotly figure object
    '''

    try:
        if all(value == 0 for value in locs['p']) == False:
            pscale = dict(type="line", 
                        x0=locs['t'][0],
                        x1=locs['t'][0], 
                        y0=locs['p'][0], 
                        y1=locs['p'][1],
                        line=dict(color="black",
                                    width=2))

            fig.add_shape(pscale, row=1, col=1)

        if all(value == 0 for value in locs['i']) == False:
            iscale = dict(type="line", 
                        x0=locs['t'][0], 
                        x1=locs['t'][0], 
                        y0=locs['i'][0], 
                        y1=locs['i'][1],
                        line=dict(color="black",
                                    width=2))

            fig.add_shape(iscale, row=2, col=1)
            
        if all(value == 0 for value in locs['t']) == False:
            tscale = dict(type="line", 
                        x0=locs['t'][0], 
                        x1=locs['t'][1], 
                        y0=locs['i'][0], 
                        y1=locs['i'][0],
                        line=dict(color="black",
                                    width=2))
            
            fig.add_shape(tscale, row=2, col=1)
    except (KeyError, TypeError):
        print("Values must be entered as space separated integers.")   
    return(fig) 

def baseline_subtract(df, window):
    '''
    This function will baseline subtract a dataframe based on a given window.

    Arguments: 
    df - a pandas dataframe with columns p, ti, tp, and i.
    window - an iterable with the start and end coordinates of the baseline window.
    
    Returns:
    df - a modified pandas dataframe.
    '''

    iblsub = []
    grouped = df.groupby('sweep')
    baselines = df.query('ti >= @window[0] and ti < @window[1]').groupby('sweep')['i'].mean()
                
    for name,group in grouped['i']:
        iblsub.append(group-baselines[name])
        
    flatList = [item for sublist in iblsub for item in sublist]
    df['i'] = flatList
    
    return(df)

def sweep_summary(df, window, param):
    '''
    This function will summarize sweep data based on a selected summary statistic.

    Arguments: 
    df - a pandas dataframe with columns p, ti, tp, sweep, and i.
    window - an iterable with the start and end coordinates of the baseline window.
    param - a summary statistic by which to summarize the data ('Max', 'Min' or 'Mean' currently accepted).
    
    Returns:
    df - a dataframe of summary data by sweep.
    '''

    subsetDf = df.query('ti >= @window[0] and ti < @window[1]')
    groups = subsetDf.groupby('sweep')

    i_thalf = np.zeros(len(groups))
    for i, grp in df.groupby('sweep'):
        i_thalf[i-1] = grp['i'][grp['ti'] == 250.0]   ########  Change this number if you want to change where you measure your current #######

    if param == 'None':
        return
    elif param == 'Mean':
        iMean = groups['i'].mean()
        summaryDict = {
            'pressure': np.abs(groups['p'].median()),
            'mean_i': iMean,
            'mean_norm_i': np.abs(iMean)/np.max(np.abs(iMean)),
            'stdev_i': groups['i'].std()
        }

        summaryDf = pd.DataFrame(summaryDict)

    elif param == 'Min':
        iMin = groups['i'].min()
        summaryDict = {
            'pressure': np.abs(groups['p'].median()),
            'min_i': iMin,
            'min_norm_i': iMin/np.min(iMin),
            'i_thalf': i_thalf,
            'inactivation': i_thalf/iMin
        }

        summaryDf = pd.DataFrame(summaryDict)
    else:
        iMax = groups['i'].max()
        summaryDict = {
            'pressure': np.abs(groups['p'].median()),
            'max_i': iMax,
            'max_norm_i': iMax/np.max(iMax)
        }

        summaryDf = pd.DataFrame(summaryDict)
    return summaryDf

def plot_summary(df, yval):
    '''
    This function will plot a dataframe of summary statistics as a function of stimulus intensity.

    Arguments: 
    df - a pandas dataframe with columns pressure, param, and normalized_param.
    
    Returns:
    fig - a plotly figure object.
    '''

    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(mode='markers',
                   name='p50', 
                   marker_color='#FF3300', 
                   marker_line_width = 1,
                   marker_size = 5,
                   x=df['pressure'], 
                   y=df[yval],
                   hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
                   )
    )

    fig.update_xaxes(title_text='Pressure (-mm Hg)')
    fig.update_yaxes(title_text='I/Imax')

    fig.update_layout(
        height=400,
        width=400,
        template='simple_white',
        showlegend=False,
        hovermode='closest')


    return(fig)

def sigmoid_fit(p, p50, k):
    '''
    This function defines a sigmoid curve.

    Arguments: 
    p - the abscissa data.
    p50 - the inflection point of the sigmoid.
    k - the slope at the inflection point of a sigmoid.
    
    Returns:
    The ordinate for a boltzmann sigmoid with the passed parameters.
    '''

    return(1 / (1 + np.exp((p50 - p) / k)))

def fit_layer(df, fig, fit):
    '''
    This function plots fit data over an existing plot.

    Arguments: 
    df - a pandas dataframe with columns pressure, param, and normalized_param.
    fig - a plotly figure object.
    fit - the fit parameters for a sigmoid fit.
    
    Returns:
    df - a plotly figure object.
    '''

    xfine = np.linspace(min(df.pressure),max(df.pressure), 100)
    fig.add_trace(
    go.Scatter(mode='lines',
               name='fit', 
               marker_color='black', 
               marker_line_width = 1,
               x=xfine, 
               y=sigmoid_fit(xfine, *fit),
               hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
               )
    )

    return(fig)

def isolate_opening(df, sweepnum, window):
    subsetDf = df.query('sweep == @sweepnum')
    subsetDf = subsetDf.query('ti >= @window[0] and ti < @window[1]')
    return subsetDf

def ngauss_guesses(x, y, nGauss):
    initial_guesses = {"p":[1], "u": [x[np.argmax(y)]], "s": [0.5]}
    for i in list(range(0, nGauss - 1)):
        initial_guesses["p"].append(0.5 * initial_guesses["p"][i])
        initial_guesses["u"].append(-2.2 * (i+1) + initial_guesses["u"][i])
        initial_guesses["s"].append(2 * initial_guesses["s"][i])

    arr = [np.array(initial_guesses['p']), np.array(initial_guesses['u']), np.array(initial_guesses['s'])]

    return(arr)
    
def single_gauss_fit(x, a1, m1, s1):
    gauss = a1 * norm.pdf(x, loc = m1, scale = s1)

    return gauss

def double_gauss_fit(x, a1, a2, m1, m2, s1, s2):
    gauss = a1 * norm.pdf(x, loc = m1, scale = s1)
    gauss += a2 * norm.pdf(x, loc = m2, scale = s2)

    return gauss

def triple_gauss_fit(x, a1, a2, a3, m1, m2, m3, s1, s2, s3):
    gauss = a1 * norm.pdf(x, loc = m1, scale = s1)
    gauss += a2 * norm.pdf(x, loc = m2, scale = s2)
    gauss += a3 * norm.pdf(x, loc = m3, scale = s3)

    return gauss

def frequency_histogram(df, nbins, ngauss = 2):
    range_x = np.max(df.i) - np.min(df.i)
    #bin_width = 2*iqr(df.i)*len(df.i)**(-1/3) ## Freedman and Diaconis method
    #nbins = round(range_x/bin_width)
    bin_width = range_x/nbins
    [y, x]=np.histogram(df.i, nbins, density=True)
    test = ngauss_guesses(x, y, ngauss)

    fig = go.Figure([go.Bar(x=x[0:-1]+0.5*bin_width, y=y, marker_color = "black")])
    
    fig.update_xaxes(title_text='Current (pA)')
    fig.update_yaxes(title_text='Density')

    fig.update_layout(
        height=600,
        width=600,
        template='simple_white',
        showlegend=False,
        hovermode='closest')

    if ngauss == 3:
        popt, pcov = curve_fit(triple_gauss_fit, x[0:-1]+0.5*bin_width, y, p0=test)
        xfine = np.linspace(min(df.i), max(df.i), 500)

        fig.add_trace(
            go.Scatter(mode='lines',
                name='fit',
                marker_color='orange',
                marker_line_width = 1,
                fill = 'tozeroy',
                x=xfine,
                y=single_gauss_fit(xfine, *popt[[0,3,6]]),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
            )
        )

        fig.add_trace(
            go.Scatter(mode='lines',
                name='fit',
                marker_color='purple',
                marker_line_width = 1,
                fill = 'tozeroy',
                x=xfine,
                y=single_gauss_fit(xfine, *popt[[1,4,7]]),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
            )
        )

        fig.add_trace(
            go.Scatter(mode='lines',
                name='fit',
                marker_color='red',
                marker_line_width = 1,
                fill = 'tozeroy',
                x=xfine,
                y=single_gauss_fit(xfine, *popt[[2,5,8]]),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
            )
        )

    else:
        popt, pcov = curve_fit(double_gauss_fit, x[0:-1]+0.5*bin_width, y, p0=test)
        xfine = np.linspace(min(df.i), max(df.i), 500)

        fig.add_trace(
            go.Scatter(mode='lines',
                name='fit',
                marker_color='orange',
                marker_line_width = 1,
                fill = 'tozeroy',
                x=xfine,
                y=single_gauss_fit(xfine, *popt[[0,2,4]]),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
            )
        )

        fig.add_trace(
            go.Scatter(mode='lines',
                name='fit',
                marker_color='purple',
                marker_line_width = 1,
                fill = 'tozeroy',
                x=xfine,
                y=single_gauss_fit(xfine, *popt[[1,3,5]]),
                hovertemplate='x: %{x}<br>' + 'y: %{y}<br>'
            )
        )

    return(fig, popt, pcov)