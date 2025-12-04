module adder(input [3:0] a, input [3:0] b, output [4:0] sum);
  assign sum = a + b;
endmodule

module chip_top(input [3:0] a, input [3:0] b, output [4:0] result);
  adder u1 (.a(a), .b(b), .sum(result));
endmodule