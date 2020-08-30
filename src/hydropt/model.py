import numpy as np

from hydropt.core import kron_index, kron_indices
from hydropt.action import PowerPlantActions, PowerPlantAction


class BasinLevels():
    """The basin levels correspond to the fill-levels of a basin given its 
    linearly spaced volume states.
    """
    
    def __init__(self, empty, full=None, basin=None, vol_to_level_lut=None, 
                 basin_shape='wedge'):
        
        self.basin = basin
        self.empty = empty
        
        if full is None:
            self.full = empty
        else:
            self.full = full
            
        if vol_to_level_lut is None:
            self.vol_to_level_lut = self.compute_vol_to_level_lut(basin_shape)
        else:
            self.vol_to_level_lut = vol_to_level_lut
        
        
    def compute_vol_to_level_lut(self, basin_shape='wedge'):
        
        vols = np.linspace(0, self.basin.volume, self.basin.num_states)
        
        if basin_shape == 'wedge':
            
            if self.empty < self.full:
                
                height = self.full - self.empty
                A = height**2 # width = 2*height
                length = self.basin.volume/A
                
                levels = np.sqrt(vols/length)+self.empty
                
            else:
                levels = self.empty*np.ones(self.basin.num_states)
                
            
        else:
            raise ValueError(f"Basin shape '{basin_shape}' not implemented. "
                             "Choose from the following models ['wegde', ]")
            
        return np.stack((vols, levels)).T
        
    @property
    def values(self):
        
        if self.basin is None:
            
            return np.array()
            
        else:
            
            vols = np.linspace(0, self.basin.volume, self.basin.num_states)
            
            vols_p = self.vol_to_level_lut[:,0]
            levels_p = self.vol_to_level_lut[:,1]
            
            return np.interp(vols, vols_p, levels_p)

        
    def __repr__(self):
        return f"BasinLevels(basin='{self.basin}', {self.values})"


class Basin():
    """The basin is a reservoir of water. Each basin specifies a discrete set 
    of states. The state space of the power plant is defined by the tensor
    product between the states of the individual basins.
    """
    
    def __init__(self, name, volume, num_states, init_volume, levels, power_plant=None):
        self.name = name
        self.volume = volume
        self.num_states = num_states
        
        #TODO: move initial volume to scenario spec
        self.init_volume = init_volume
        
        self.levels = levels
        
        self.power_plant = power_plant
        
    @property
    def levels(self):
        return self._levels
        
    @levels.setter
    def levels(self, levels):
        if isinstance(levels, BasinLevels):
            self._levels = levels
            self._levels.basin = self
        elif isinstance(levels, tuple):
            self._levels = BasinLevels(empty=levels[0], full=levels[1], basin=self)
        else:
            self._levels = BasinLevels(levels, basin=self)
            
    def kron_levels(self):
        if self.power_plant is None:
            return self._levels.empty
        else:
            basin_num_states = self.power_plant.basin_num_states()
            index = self.power_plant.basin_index(self)
            return self._levels.values[kron_index(basin_num_states, index)]
        
    def __repr__(self):
        return f"Basin('{self.name}')"

    
class Outflow(Basin):
    def __init__(self, outflow_level, name='Outflow'):
        super().__init__(volume=1, num_states=2, init_volume=0, levels=outflow_level, name=name)
        

 
class Turbine():
    """The turbine characterices the amount of power that is generated when 
    water flows from the upper to the lower basin.
    """
    
    def __init__(self, name, max_power, base_load, 
                 upper_basin, lower_basin, efficiency):
        self.name = name
        self.max_power = max_power
        self.base_load = base_load
        self.upper_basin = upper_basin
        self.lower_basin = lower_basin
        
        self.efficiency = efficiency
    
    def head(self):
        return self.upper_basin.kron_levels() - self.lower_basin.kron_levels()
    
    def power(self, flow_rate):
        return self.efficiency*(1000*9.81)*self.head()*flow_rate
    
    def flow_rate(self, power):
        return (power/(self.efficiency*(1000*9.81)))/self.head()
    
    def __repr__(self):
        return f"Turbine('{self.name}')"
   

    
class PowerPlant():
    def __init__(self, basins=None, turbines=None, actions=None, constraints=None):
        self.basins = basins    
        self.turbines = turbines
        self._actions = actions
        self.constraints = constraints
        
    @property
    def basins(self):
        return self._basins
    
    @basins.setter
    def basins(self, basins):
        for basin in basins:
            basin.power_plant = self
        self._basins = basins
            
    def basin_index(self, basin):
        try:
            return self.basins.index(basin)
        except ValueError:
            return None # intended for outflow basin
        
    def basin_volumes(self):
        return np.array([basin.volume for basin in self.basins])
    
    def basin_num_states(self):
        return np.array([basin.num_states for basin in self.basins])
    
    def basin_init_volumes(self):
        return np.array([basin.init_volume for basin in self.basins])
    
    def basin_names(self):
        return [basin.names for basin in self.basins]
    
    def num_states(self):
        return np.prod(self.basin_num_states())
    
    def turbine_actions(self):
        actions = list()
        for turbine in self.turbines:
            actions.append([a for a in self._actions if a.turbine is turbine])
        return actions
        
    def actions(self):
        turbine_actions = self.turbine_actions()
        num_actions = [len(a) for a in turbine_actions]
        combinations = kron_indices(num_actions, range(len(num_actions)))
        power_plant_actions = []
        for comb in combinations:
            group = []
            for k in range(len(comb)):
                group.append(turbine_actions[k][comb[k]])
            power_plant_actions.append(PowerPlantAction(group, self))
        return PowerPlantActions(power_plant_actions)
    
            

        
        