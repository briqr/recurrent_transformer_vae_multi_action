import os
import torch
from torch.utils.tensorboard import SummaryWriter

from torch.utils.data import DataLoader
from src.train.trainer import train
from src.utils.tensors import collate_multi
import src.utils.fixseed  # noqa

from src.parser.training import parser
from src.utils.get_model_and_data import get_model_and_data


def do_epochs(model, datasets, parameters, optimizer, writer):
    dataset = datasets["train"]
    train_iterator = DataLoader(dataset, batch_size=parameters["batch_size"],
                                shuffle=True, num_workers=0, collate_fn=collate_multi)

    logpath = os.path.join(parameters["folder"], "training.log")
    with open(logpath, "w") as logfile:
        for epoch in range(1, parameters["num_epochs"]+1):
            print('**new epoch ** %d' %epoch)
            dict_loss = train(model, optimizer, train_iterator, model.device)

            for key in dict_loss.keys():
                dict_loss[key] /= len(train_iterator)
                writer.add_scalar(f"Loss/{key}", dict_loss[key], epoch)

            epochlog = f"Epoch {epoch}, train losses: {dict_loss}"
            print(epochlog)
            print(epochlog, file=logfile)

            if ((epoch % parameters["snapshot"]) == 0) or (epoch == parameters["num_epochs"]):
                checkpoint_path = os.path.join(parameters["folder"],
                                               'checkpoint_{:04d}.pth.tar'.format(epoch))
                print('Saving checkpoint {}'.format(checkpoint_path))
                torch.save(model.state_dict(), checkpoint_path)

            writer.flush()


if __name__ == '__main__':
    # parse options
    parameters = parser()
    
    
    # logging tensorboard
    writer = SummaryWriter(log_dir=parameters["folder"])

    model, datasets = get_model_and_data(parameters)

    # optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=parameters["lr"])

    print('Total params: %.2fM' % (sum(p.numel() for p in model.parameters()) / 1000000.0))
    print("Training model..")
    do_epochs(model, datasets, parameters, optimizer, writer)

    writer.close()
