
module simple_alu(input [7:0] a, input [7:0] b, input [1:0] op, output reg [7:0] y);
  always @* begin
    case (op)
      2'b00: y = a + b;
      2'b10: y = a ^ b;
      default: y = a & b;
    endcase
  end
endmodule

module simple_rom(input [0:0] addr, output reg [7:0] data);
  always @* begin
    case (addr)
      1'b0: data = 8'h2A;
      1'b1: data = 8'h11;
      default: data = 8'h00;
    endcase
  end
endmodule
