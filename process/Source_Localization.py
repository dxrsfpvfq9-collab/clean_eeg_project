#SOURCE LOCALIZATION
import numpy as np
import matplotlib.pyplot as plt
import mne
import os
os.environ['ETS_TOOLKIT'] = 'qt4'

#import imp
#try:
#    imp.find_module('PySide') # test if PySide if available
#except ImportError:
#    os.environ['QT_API'] = 'pyqt5' # signal to pyface that PyQt4 should be used

#from pyface.qt import QtGui, QtCore


#from mayavi import mlab
import pyvista as pv
import csv
import math
import pyvistaqt as pvqt
from PyQt5.QtWidgets import QApplication, QMainWindow, QSizePolicy, QPushButton, QSlider, QHBoxLayout, QWidget, QLabel, QGridLayout
from PyQt5.QtCore import Qt


def vector_matrix_multiplication(matrix, vector):
    # Verify dimensions
    if matrix.shape[1] != len(vector):
        vector = vector[:-1]
    # Initialize the output vector
    mult_result = np.zeros(matrix.shape[0])
    # Perform matrix-vector multiplication
    for i in range(matrix.shape[0]):
        mult_result[i] = np.dot(matrix[i], vector)
    
    return mult_result

def source_localization(source_point, location_matrix, max_value, max_index, reshaped_list, voxel_csd, depth, nearest_vox, source_coords, ordered_ica_mixing, matrix):
    global direction_array
    global arrows
    
    # Convert voxel coordinates to numeric values--------------------------------------------------------------------------------------------------------------------------------
    voxel_coordinates = np.array(location_matrix[:, 0:3], dtype=float)
    #print(voxel_coordinates)
    comps_source = []
    for idx in range(1, 20):
        vector1 = ordered_ica_mixing[:, idx-1]
        vector1 = vector1[:19]
        mult_result = vector_matrix_multiplication(matrix, vector1)
        print('DOT PRODUCT RESULT SHAPE: ', mult_result.shape)
        #print(mult_result)
        reshaped_list1 = np.reshape(mult_result, (6239, 3))
        print("RESHAPED LIST: ", reshaped_list1)
        #CREATE CSD BASED OFF DOT PRODUCT RESULT---------------------------------------------------------------------------------------------------------------------------------------
        voxel_csd1 = []
        for i in range(0, len(mult_result), 3):
            xyz1 = mult_result[i:i+3]
            sum_of_squares1 = sum(k**2 for k in xyz1)
            new_val1 = math.sqrt(sum_of_squares1)
            voxel_csd1.append(new_val1)
        print('CSD SHAPE: ', len(voxel_csd1))
        #FIND THE MAX----------------------------------------------------------------------------------------------------------------------------------------------------------------
        max_value1 = max(voxel_csd1)
        max_index1 = voxel_csd1.index(max_value1)
        print("Maximum value:", max_value1)
        print("Index of maximum value:", max_index1)
        #GET LOCATION OF SOURCE VOXEL-----------------------------------------------------------------------------------------------------------------------------------------------
        location_file_path = os.path.join('MNI-BAs-6239-voxels.csv')
        with open(location_file_path, 'r') as file:
            location_data1 = csv.reader(file)
            location_matrix1 = np.array(list(location_data1), dtype=str)
        #print(location_matrix)
        print('LOCATION MATRIX SHAPE: ',location_matrix1.shape)
   
        #ACQUIRE SOURCE POINT--------------------------------------------------------------------------------------------------------------------------------------------------------
        source_point1 = location_matrix1[max_index1, :]
        print('SOURCE POINT: ', source_point1) 
        voxel_coords1 = location_matrix1[:, :3]
        voxel_coordinates1 = [(int(x), int(y), int(z)) for x, y, z in voxel_coords1]
        source_coords1 = source_point1[:3]
        source_coords1 = np.array(source_coords1)
        source_coords1 = tuple(map(int, source_coords1))
        comps_source.append(source_coords1)

    print('COMPS SOURCE: ', comps_source)
    #ACQUIRE SOURCE POINT--------------------------------------------------------------------------------------------------------------------------------------------------------
   
    voxel_coords = source_point[:3]
    # Convert the coordinates to float
    voxel_coords = [float(coord) for coord in voxel_coords]
    
    print('SOURCE POINT COORDS', voxel_coords)
    reshape_val = reshaped_list[max_index, :]
    print('CORRESPONDING ELECTRICAL SIGNAL: ', reshape_val)
    # Calculate the dipole orientation as the normalized electric field vector
    dipole_orientation = reshape_val / np.linalg.norm(reshape_val)
    print('DIPOLE ORIENTATION: ', dipole_orientation)
    print('AMPLITUDE: ', max_value)
    new_amp = max_value * 1e-9
    print('NEW AMPLITUDE: ', new_amp)
    # Step 2: Load the MNE standard brain model--------------------------------------------------------------------------------------------------------------------------------------
    subject = 'fsaverage'  # Example subject name
    cwd = os.getcwd()
    subjects_dir = os.path.join(cwd, 'mne_data', 'MNE-fsaverage-data')  # Path to the subjects directory
    #mne.datasets.fetch_fsaverage(subjects_dir=subjects_dir)
    surf_left = mne.read_surface(subjects_dir + '/fsaverage/surf/lh.white')
    surf_right = mne.read_surface(subjects_dir + '/fsaverage/surf/rh.white')

    # Extract vertices and faces for both hemispheres
    vertices_left, faces_left = surf_left
    vertices_right, faces_right = surf_right

    # Combine vertices and faces for both hemispheres
    vertices = np.vstack((vertices_left, vertices_right))
    faces_right_shifted = faces_right + len(vertices_left)
    faces = np.vstack((faces_left, faces_right_shifted))

    # Step 3: Transform the voxel coordinates to the MNE standard space (if needed)
    # If the voxel coordinates are already in MNI space, you can skip this step.

    # Step 4: Overlay the voxel onto the brain model===============================================================================================================================
    # Create a figure
    if voxel_coords[0] < 0:
        hemisphere = 'lh'  # Left hemisphere
    else:
        hemisphere = 'rh'  # Right hemisphere
    #===================================================================================================================================================================================
    # Define colormap and normalize CSD values
    colormap = 'jet'  # You can choose any other colormap as per your preference
    voxel_csd = np.array(voxel_csd)
    csd_min, csd_max = voxel_csd.min(), voxel_csd.max()
    csd_normalized = (voxel_csd - csd_min) / (csd_max - csd_min)  # Normalize CSD values between 0 and 1
    opacity = 1
    
    
    # Create the points and their associated opacity values
    points = voxel_coordinates
    opacity_values = opacity * csd_normalized

    # Create a PyVista dataset for the points
    point_cloud = pv.PolyData(points)
    point_cloud['opacity'] = opacity_values

    # Plot the points with variable opacity using PyVista==============================================================================================================================
    app = QApplication([])
    window = QMainWindow()
    widget = QWidget()
    layout = QHBoxLayout(widget)
    
    global ori_list
    global coord_list
    ori_list = []
    coord_list = []
    pl = pvqt.BackgroundPlotter()
    pc_actor = pl.add_points(point_cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16, opacity='opacity')
    pl.add_text(text=('Source Region: ' + str(source_point[3:])), position='upper_right', color='orange', shadow=False, font_size=15)
    pl.add_text(text=('Depth of Signal:' + str(round(depth, 3)) + 'mm'), position=(0.8, 0.9), color='black', shadow=False, font_size=16)
    cent_array = np.array(voxel_coords)
    if depth != 0:
        lines = np.array([source_coords, nearest_vox])
        print(lines)
        pl.add_lines(lines, color='black', width=5)
    
    
    for index, source in enumerate(comps_source):
        pl.add_point_labels([source], [str(index + 1)], font_size=22, point_size=16, text_color='white')

    
    direction_array = np.array(reshape_val)
    direction_array = direction_array / (max_value / 20)
    
    ori_list.append(direction_array)
    coord_list.append(cent_array)

    interactor = pl.app_window


    actor = pl.renderer.GetActors().GetLastActor()

    opa_slider = QSlider()
    opa_slider.setOrientation(Qt.Horizontal)
    opa_slider.setRange(0, 100)
    opa_slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    opa_slider.setFixedHeight(30)

    dip_slider = QSlider()
    dip_slider.setMinimum(1)
    dip_slider.setMaximum(100)
    dip_slider.setSingleStep(1)
    dip_slider.setOrientation(Qt.Horizontal)
    # dip_slider.valueChanged.connect(slider_moved)
    dip_slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    dip_slider.setFixedHeight(30)

    # Create labels for slider names and values
    slider_labels = {
        dip_slider: QLabel("Amount of Dipoles"),
        opa_slider: QLabel("Opacity")
    }
    slider_value_labels = {
        dip_slider: QLabel(str(dip_slider.value())),
        opa_slider: QLabel(str(opa_slider.value()))
    }

    # Create a layout for the sliders, labels, and values
    # Create a layout for the sliders, labels, and values
    sliders_layout = QGridLayout()
    row = 0
    for slider, label in slider_labels.items():
        value_label = slider_value_labels[slider]
        sliders_layout.addWidget(label, row, 0)
        sliders_layout.addWidget(slider, row, 1)
        sliders_layout.addWidget(value_label, row, 2)
        row += 1

    # Add the opacity slider to the sliders layout
    #sliders_layout.addWidget(opa_slider, row, 1)

    #Add the Button
    flip_button = QPushButton('Flip Dipole')
    sliders_layout.addWidget(flip_button, row+1, 0, 1, 3)

    next_button = QPushButton('Close Brain Viewer')
    sliders_layout.addWidget(next_button, row+2, 0, 1, 3)

    # Create slider widget
    sliders_widget = QWidget()
    sliders_widget.setLayout(sliders_layout)
    arrows = []
    def update_dipoles(value):
        global arrows
        global ori_list
        global coord_list
        ori_list =[]
        coord_list =[]
        amount = value
        val_indices = np.argpartition(voxel_csd, -amount)[-amount:]
        dip_coords = voxel_coordinates[val_indices]
        ori_val = reshaped_list[val_indices]
        for val in ori_val:
            val_array = np.array(val)
            #norm_val = val_array / np.linalg.norm(val_array)
            norm_val = val_array / (max_value / 20)
            ori_list.append(norm_val)
        for coord in dip_coords:
            coord_array = np.array(coord)
            coord_list.append(coord_array)
        for arrow in arrows:
            pl.remove_actor(arrow)
        
        arrows = []

        for coord, ori in zip(coord_list, ori_list):
            arrow_actor = pl.add_arrows(cent=np.array([coord]), direction=np.array([ori]), cmap='plasma')
            arrows.append(arrow_actor)
            pl.update()
        sender = app.sender()
        if sender in slider_value_labels:
            label = slider_value_labels[sender]
            label.setText(f"{sender.value()}")
        pl.update()
        
    def update_opacity(value):
        opacity = value / 100.0
        pc_actor.GetProperty().SetOpacity(opacity)
        sender = app.sender()
        if sender in slider_value_labels:
            label = slider_value_labels[sender]
            label.setText(f"{sender.value()}")
        pl.update()

    def flip_dipole():
        global arrows
        print('flipped')
        new_arrows = []
        for arrow, ori, coord in zip(arrows, ori_list, coord_list):
            ori *= -1
            pl.remove_actor(arrow)
            arrow_actor = pl.add_arrows(cent=np.array([coord]), direction=np.array([ori]), cmap='plasma')
            new_arrows.append(arrow_actor)
        arrows = new_arrows 
        pl.update()
    
    def next_view():
        window.close()

    '''
    def on_button_click(event):
        if event.inaxes == axes[0]:
            # Clicked on the first scatter plot (X slice)
            slice_points = x_slice_points
            slice_index = 0
        elif event.inaxes == axes[1]:
            # Clicked on the second scatter plot (Y slice)
            slice_points = y_slice_points
            slice_index = 1
        elif event.inaxes == axes[2]:
            # Clicked on the third scatter plot (Z slice)
            slice_points = z_slice_points
            slice_index = 2
        else:
            # Clicked outside of the scatter plots, do nothing
            return
    
        # Get the coordinates of all the selected points on the slice
        x, y, z = slice_points[:, 0], slice_points[:, 1], slice_points[:, 2]

        # Find the indices of voxels with the same coordinate along the clicked slice dimension
        voxel_indices = np.where(np.isclose(voxel_coords[slice_index], voxel_coordinates[:, slice_index]))

        # Get the CSD values of the corresponding voxels
        voxel_csd_values = voxel_csd[voxel_indices]

        mlab.clf()
        
        # Plot the brain surfaces again
        mlab.triangular_mesh(vertices[:, 0], vertices[:, 1], vertices[:, 2], faces, color=(0.5, 0.5, 0.5), opacity=0.3)
        
        # Create voxel cubes for all the selected points with respective colors
        mlab.points3d(x, y, z, voxel_csd_values, mode='cube', colormap='jet', scale_factor=3.0, scale_mode='none')

        # Define the endpoints for the lines
        endpoints_x = np.array([voxel_coords[0] + 200, voxel_coords[1], voxel_coords[2]])
        endpoints_y = np.array([voxel_coords[0], voxel_coords[1] + 200, voxel_coords[2]])
        endpoints_z = np.array([voxel_coords[0], voxel_coords[1], voxel_coords[2] + 200])

        # Plot the lines using Mayavi
        mlab.plot3d([voxel_coords[0] - 200, endpoints_x[0]], [voxel_coords[1], endpoints_x[1]], [voxel_coords[2], endpoints_x[2]], color=(1, 0, 1), tube_radius=None, line_width=2)
        mlab.plot3d([voxel_coords[0], endpoints_y[0]], [voxel_coords[1] - 200, endpoints_y[1]], [voxel_coords[2], endpoints_y[2]], color=(0, 1, 0), tube_radius=None, line_width=2)
        mlab.plot3d([voxel_coords[0], endpoints_z[0]], [voxel_coords[1], endpoints_z[1]], [voxel_coords[2] - 200, endpoints_z[2]], color=(0, 0, 1), tube_radius=None, line_width=2)

        # Redraw the Mayavi scene to update the display
        mlab.draw()
        '''


    opa_slider.valueChanged.connect(update_opacity)
    flip_button.clicked.connect(flip_dipole)
    dip_slider.valueChanged.connect(update_dipoles)
    next_button.clicked.connect(next_view)
    
    for ori, coord in zip(ori_list, coord_list):
        arrow_actor = pl.add_arrows(cent=coord, direction=ori, cmap='plasma')
        arrows.append(arrow_actor)
    layout.addWidget(sliders_widget)
    layout.addWidget(interactor)
    #widget.setLayout(layout)
    window.setCentralWidget(widget)
    window.show()

    app.exec_()

    '''
    # Plot the brain surfaces using Mayavi
    mlab.figure(size=(800, 800), bgcolor=(0, 0, 0))
    mlab.triangular_mesh(vertices[:, 0], vertices[:, 1], vertices[:, 2], faces, color=(0.5, 0.5, 0.5), opacity=0.3)

    # Assuming you have already defined voxel_coords as (x, y, z) for the point inside the brain
    mlab.points3d(voxel_coords[0], voxel_coords[1], voxel_coords[2], color=(1, 0, 0), scale_factor=6)

    # Define the endpoints for the lines
    endpoints_x = np.array([voxel_coords[0] + 200, voxel_coords[1], voxel_coords[2]])
    endpoints_y = np.array([voxel_coords[0], voxel_coords[1] + 200, voxel_coords[2]])
    endpoints_z = np.array([voxel_coords[0], voxel_coords[1], voxel_coords[2] + 200])

    # Plot the lines using Mayavi
    mlab.plot3d([voxel_coords[0] - 200, endpoints_x[0]], [voxel_coords[1], endpoints_x[1]], [voxel_coords[2], endpoints_x[2]], color=(1, 0, 1), tube_radius=None, line_width=2)
    mlab.plot3d([voxel_coords[0], endpoints_y[0]], [voxel_coords[1] - 200, endpoints_y[1]], [voxel_coords[2], endpoints_y[2]], color=(0, 1, 0), tube_radius=None, line_width=2)
    mlab.plot3d([voxel_coords[0], endpoints_z[0]], [voxel_coords[1], endpoints_z[1]], [voxel_coords[2] - 200, endpoints_z[2]], color=(0, 0, 1), tube_radius=None, line_width=2)


    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(4, 8))

    # Display x, y, and z slices with appropriate colors
    #location_matrix = np.array([row[:3] for row in location_matrix], dtype=float)

    x = voxel_coordinates[:, 0]
    y = voxel_coordinates[:, 1]
    z = voxel_coordinates[:, 2]
    
    x_slice_points = voxel_coordinates[np.isclose(x, voxel_coords[0])]
    y_slice_points = voxel_coordinates[np.isclose(y, voxel_coords[1])]
    z_slice_points = voxel_coordinates[np.isclose(z, voxel_coords[2])]

    axes[0].scatter(x_slice_points[:, 1], x_slice_points[:, 2], c=voxel_csd[np.isclose(x, voxel_coords[0])], cmap='jet', marker='s')
    axes[0].scatter(voxel_coords[1], voxel_coords[2], color='red')
    axes[0].set_title('X slice')
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    axes[0].set_xticklabels([])
    axes[0].set_yticklabels([])
    axes[0].set_aspect(.95)

    axes[1].scatter(y_slice_points[:, 0], y_slice_points[:, 2], c=voxel_csd[np.isclose(y, voxel_coords[1])], cmap='jet', marker='s')
    axes[1].scatter(voxel_coords[0], voxel_coords[2], color='red')
    axes[1].set_title('Y slice')
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    axes[1].set_xticklabels([])
    axes[1].set_yticklabels([])
    axes[1].set_aspect(1)

    axes[2].scatter(z_slice_points[:, 0], z_slice_points[:, 1], c=voxel_csd[np.isclose(z, voxel_coords[2])], cmap='jet', marker='s')
    axes[2].scatter(voxel_coords[0], voxel_coords[1], color='red')
    axes[2].set_title('Z slice')
    axes[2].set_xticks([])
    axes[2].set_yticks([])
    axes[2].set_xticklabels([])
    axes[2].set_yticklabels([])
    axes[2].set_aspect(1.1)
# Show the plot
    
    fig.canvas.mpl_connect('button_press_event', on_button_click)
    
    plt.tight_layout()
    plt.show()
    
    mlab.show()
    '''