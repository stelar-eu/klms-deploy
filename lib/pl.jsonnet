
local obj = {
    a1: {
        a2: {
            a3: {
                a4: 4,
                a5: 5
            },
            b3: 103
        },
        b2: 102
    },
    b1: 101,
    ['cc%03d' % 11] : 1000,
    add(y):: 
        local z = self.a1.a2.a3.a4 + y;
        self {
            //local base_obj=super.a,
            a1+: { a2+: { a3+: {
                a4: z
            } } }
        }


};


{
    result: obj.add(10)
}