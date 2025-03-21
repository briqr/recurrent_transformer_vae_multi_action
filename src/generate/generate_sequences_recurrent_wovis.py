import os

import matplotlib.pyplot as plt
import torch
import numpy as np
import cv2
from src.utils.get_model_and_data import get_model_and_data
from src.models.get_model import get_model
from src.models.smpl import SMPL,SMPLX, JOINTSTYPE_ROOT
from src.render.renderer import get_renderer


from src.parser.generate import parser
#from src.utils.fixseed import fixseed # noqa

plt.switch_backend('agg')
#fixseed(1071)
def generate_actions(beta, model, dataset, epoch, params, folder, data_i, num_frames=60,
                     durationexp=False, vertstrans=True, onlygen=False, nspa=10, inter=False, writer=None):
    """ Generate & viz samples """

    x = False

    # visualize with joints3D
    model.outputxyz = True
    # print("remove smpl")
    model.param2xyz["jointstype"] = "vertices"

    fact = params["fact_latent"]
    num_classes = dataset.num_classes + 100
    #todo 
    num_classes = 1
    classes = torch.arange(num_classes)
    #classes = torch.from_numpy(np.asarray([0,0,0,0,0,0,0]))
    if not onlygen:
        nspa = 1

    nats = num_classes
    num_frames = 180
    durationexp = False
    if durationexp:
        nspa = 4
        durations = [40, 60, 80, 100]
        gendurations = torch.tensor([[dur for cl in classes] for dur in durations], dtype=int)
    else:
        gendurations = torch.tensor([num_frames for cl in classes], dtype=int)
    
    #real_samples, mask_real, real_lengths, labels, act_time_stamps, frame_act_map = dataset.get_label_sample_batch(classes.numpy())
    real_samples, mask_real, real_lengths, labels, act_time_stamps, frame_act_map = dataset.get_label_sample_ind(data_i)
    gendurations = torch.tensor([real_lengths[0] for cl in classes], dtype=int)


        # to visualize directly
    classes = labels
    if not onlygen:
        # extract the real samples
        
        #print('classes', classes)
        # Visualizaion of real samples
        visualization = {"x": real_samples.to(model.device),
                         "y": classes.to(model.device),
                         "mask": mask_real.to(model.device),
                         "lengths": real_lengths.to(model.device),
                         "output": real_samples.to(model.device),
                         "action_timestamps": act_time_stamps,
                         "frame_act_map": frame_act_map}

        reconstruction = {"x": real_samples.to(model.device),
                          "y": classes.to(model.device),
                          "lengths": real_lengths.to(model.device),
                          "mask": mask_real.to(model.device),
                          "action_timestamps": act_time_stamps,
                          "frame_act_map": frame_act_map}
 
    print("Computing the samples poses..")

    # generate the repr (joints3D/pose etc)
    model.eval()
    with torch.no_grad():
        if not onlygen:
            # Get xyz for the real ones
            visualization["output_xyz"] = model.rot2xyz(visualization["output"],
                                                        visualization["mask"],
                                                        vertstrans=vertstrans,
                                                        beta=beta)

            # Reconstruction of the real data
            #reconstruction = model(reconstruction)  # update reconstruction dicts

            noise_same_action = "random"
            noise_diff_action = "random"

            # Generate the new data
        
            generation = model.generate(classes, gendurations, nspa=nspa,
                                        noise_same_action=noise_same_action,
                                        noise_diff_action=noise_diff_action,
                                        fact=fact, action_timestamps=act_time_stamps, frame_act_map= frame_act_map)

            generation["output_xyz"] = model.rot2xyz(generation["output"],
                                                     generation["mask"], vertstrans=vertstrans,
                                                     beta=beta)

            # outxyz = model.rot2xyz(reconstruction["output"],
            #                        reconstruction["mask"], vertstrans=vertstrans,
            #                        beta=beta)
            # reconstruction["output_xyz"] = outxyz
        else:
            if inter:
                noise_same_action = "interpolate"
            else:
                noise_same_action = "random"

            noise_diff_action = "random"

            # Generate the new data
            generation = model.generate(classes, gendurations, nspa=nspa,
                                        noise_same_action=noise_same_action,
                                        noise_diff_action=noise_diff_action,
                                        fact=fact, action_timestamps=act_time_stamps, frame_act_map= frame_act_map)

            generation["output_xyz"] = model.rot2xyz(generation["output"],
                                                     generation["mask"], vertstrans=vertstrans,
                                                     beta=beta)
            output = generation["output_xyz"].reshape(nspa, nats, *generation["output_xyz"].shape[1:]).cpu().numpy()

    if not onlygen: #todo
        output = np.stack([visualization["output_xyz"].cpu().numpy(),
                           generation["output_xyz"].cpu().numpy()])#,
                           #reconstruction["output_xyz"].cpu().numpy()])

    output_dict = {'classes' : classes, 'pose': generation["output"], 'vert': generation['output_xyz']}
    
    return output_dict


def main():
    parameters, folder, checkpointname, epoch = parser()
    nspa = parameters["num_samples_per_action"]

    # no dataset needed
    if parameters["mode"] in []:   # ["gen", "duration", "interpolate"]:
        model = get_model(parameters)
    else:
        model, datasets = get_model_and_data(parameters)
        dataset = datasets["train"]  # same for ntu

    print("Restore weights..")
    checkpointpath = os.path.join(folder, checkpointname)
    state_dict = torch.load(checkpointpath, map_location=parameters["device"])
    model.load_state_dict(state_dict)

    #from src.utils.fixseed import fixseed  # noqa
    #for seed in [1,2,3,4,5,67,8,9,10, 13, 14, 15, 16, 17, 18, 19, 20,21,22]:  # [0, 1, 2]:
    #
    print(f"Visualization of the epoch {epoch}")
    #fixseed(101167)
    all_outputs = []    
    for i in range(0, dataset.__len__()):
        #data_i = np.random.randint(0,len(dataset._train))
        data_i = i
        # visualize_params
        onlygen = True
        
        vertstrans = False
        inter = True and onlygen
        varying_beta = False
        if varying_beta:
            betas = [-2, -1, 0, 1, 2]
        else:
            betas = [0]
        for beta in betas:
            output = generate_actions(beta, model, dataset, epoch, parameters,
                                      folder, data_i, inter=inter, vertstrans=vertstrans,
                                      nspa=nspa, onlygen=onlygen)
            all_outputs.append(output)
    if True:
        if varying_beta:
            filename = "generation_beta_{}.npy".format(beta)
        else:
            filename = "generation.npy"

        filename = os.path.join(folder, filename)
        np.save(filename, all_outputs)
        print("Saved at: " + filename)


if __name__ == '__main__':
    main()
