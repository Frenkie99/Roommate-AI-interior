import { motion } from 'framer-motion';
import clsx from 'clsx';
import { 
  Sofa, Bed, ChefHat, UtensilsCrossed, Bath, 
  BookOpen, Baby, Sun, DoorOpen 
} from 'lucide-react';

const ROOM_TYPES = [
  { id: 'living_room', name: '客厅', icon: Sofa },
  { id: 'bedroom', name: '卧室', icon: Bed },
  { id: 'master_bedroom', name: '主卧', icon: Bed },
  { id: 'kitchen', name: '厨房', icon: ChefHat },
  { id: 'dining_room', name: '餐厅', icon: UtensilsCrossed },
  { id: 'bathroom', name: '卫生间', icon: Bath },
  { id: 'study', name: '书房', icon: BookOpen },
  { id: 'kids_room', name: '儿童房', icon: Baby },
  { id: 'balcony', name: '阳台', icon: Sun },
  { id: 'entrance', name: '玄关', icon: DoorOpen },
];

export default function RoomTypeSelector({ selected, onSelect }) {
  return (
    <div className="flex flex-wrap gap-2">
      {ROOM_TYPES.map((room) => {
        const Icon = room.icon;
        return (
          <motion.button
            key={room.id}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onSelect(room.id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
              selected === room.id
                ? 'bg-primary-600 text-white shadow-lg shadow-primary-500/25'
                : 'bg-neutral-800/50 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200'
            )}
          >
            <Icon className="w-4 h-4" />
            {room.name}
          </motion.button>
        );
      })}
    </div>
  );
}
